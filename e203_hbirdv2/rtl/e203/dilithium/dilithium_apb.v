module dilithium_apb #(
    parameter IN_AW  = 12,               // 输入缓冲 4096 x 32b = 16KB（lv5+3300B 消息需要 2626 字）
    parameter OUT_AW = 11                // 输出缓冲 2048 x 32b = 8KB
)(
    input  wire        PCLK, PRESETn,
    input  wire [31:0] PADDR,
    input  wire        PSEL, PENABLE, PWRITE,
    input  wire [31:0] PWDATA,
    output reg  [31:0] PRDATA,
    output wire        PREADY,           // 恒 1，无等待
    output wire        irq_o
);

    // ---------------- 寄存器组 ----------------
    // 0x00 CTRL  [0]start(自清零) [2:1]mode [6:4]sec_lvl
    // 0x04 STATUS [0]busy [1]done [2]result(verify:1=拒绝)；写此地址清 done
    // 0x08 MLEN   0x0C IEN [0]irq使能
    // 0x10 PTR(输入缓冲写指针) 0x14 WDATA(写后ptr+1)
    // 0x18 RPTR(输出缓冲读指针) 0x1C RDATA(读后ptr+1)
    reg [31:0] ctrl;
    reg [31:0] mlen;
    reg [31:0] ien;
    reg        busy, done, result;
    reg [IN_AW-1:0]  wptr;
    reg [OUT_AW-1:0] rptr;
    // 缓冲拆偶奇双 bank，各用 dual_port_ram 实例实现（综合映射 Block RAM）：
    // inbuf_hi[k]=偶字 inbuf[2k]，inbuf_lo[k]=奇字 inbuf[2k+1]，outbuf 同理
    wire [31:0] inbuf_hi_dob, inbuf_lo_dob, outbuf_hi_dob, outbuf_lo_dob;

    assign PREADY = 1'b1;
    wire wr = PSEL & PENABLE &  PWRITE;
    wire rd = PSEL & PENABLE & ~PWRITE;

    always @(posedge PCLK or negedge PRESETn) begin
        if (!PRESETn) begin
            ctrl <= 0; mlen <= 0; ien <= 0; wptr <= 0; rptr <= 0;
        end else begin
            if (wr && !busy) case (PADDR[7:0])
                8'h00: ctrl <= PWDATA;
                8'h08: mlen <= PWDATA;
                8'h0C: ien  <= PWDATA;
                8'h10: wptr <= PWDATA[IN_AW-1:0];
                8'h14: wptr <= wptr + 1'b1;
                8'h18: rptr <= PWDATA[OUT_AW-1:0];
            endcase
            else if (ctrl[0]) ctrl[0] <= 1'b0;
            if (rd && PADDR[7:0]==8'h1C) rptr <= rptr + 1'b1;   // 读输出缓冲后指针自增（与写 0x18 互斥：APB 单周期不会同时读写）
        end
    end

    always @(posedge PCLK) begin
        if (rd) case (PADDR[7:0])
            8'h00: PRDATA <= ctrl;
            8'h04: PRDATA <= {29'b0, result, done, busy};
            8'h08: PRDATA <= mlen;
            8'h1C: PRDATA <= rptr[0] ? outbuf_lo_dob : outbuf_hi_dob;  // RAM 读地址建立阶段已给，访问阶段 dob 有效
            default: PRDATA <= 32'h0;
        endcase
    end

    assign irq_o = ien[0] & done;

    // ---------------- 字数表（n_in 按 64b 字，n_out 按 32b 字）----------------
    // mode: 0=keygen 1=verify 2=sign；sec_lvl: 2/3/5
    wire [1:0]  mode_w = ctrl[2:1];
    wire [15:0] n_z  = (ctrl[6:4]==3'd2) ? 16'd288 : (ctrl[6:4]==3'd3) ? 16'd400 : 16'd560;
    wire [15:0] n_t1 = (ctrl[6:4]==3'd2) ? 16'd160 : (ctrl[6:4]==3'd3) ? 16'd240 : 16'd320;
    wire [15:0] n_h  = (ctrl[6:4]==3'd2) ? 16'd11  : (ctrl[6:4]==3'd3) ? 16'd8   : 16'd11;
    wire [15:0] n_s1 = (ctrl[6:4]==3'd2) ? 16'd48  : (ctrl[6:4]==3'd3) ? 16'd80  : 16'd84;
    wire [15:0] n_s2 = (ctrl[6:4]==3'd2) ? 16'd48  : (ctrl[6:4]==3'd3) ? 16'd96  : 16'd96;
    wire [15:0] n_t0 = (ctrl[6:4]==3'd2) ? 16'd208 : (ctrl[6:4]==3'd3) ? 16'd312 : 16'd416;
    wire [15:0] n_m  = ({6'b0, mlen[15:0]} + 16'd7) >> 3;  // ceil(mlen/8)
    // keygen: 仅 seed(4)
    // sign:   rho(4)+mlen(1)+tr(4)+m(n_m)+k(4)+s1+s2+t0
    // verify: rho(4)+c(4)+z+t1+mlen(1)+m(n_m)+h
    wire [15:0] n_in = (mode_w==2'd0) ? 16'd4 :
                       (mode_w==2'd2) ? 16'd13 + n_m + n_s1 + n_s2 + n_t0 :
                                        16'd9 + n_z + n_t1 + n_m + n_h;
    // n_out 按 32b 字计：每个 64b 输出字拆写两个 outbuf 项（高 32 位在前，字内大端）
    // keygen: rho+k+s1+s2+t1+t0+tr = 476/740/928 (64b) -> 952/1480/1856
    // sign:   z+h+c = 303/412/575 (64b)              -> 606/824/1150
    // verify: 1 (64b)                                -> 2
    wire [15:0] n_out = (mode_w==2'd0) ? ((ctrl[6:4]==3'd2) ? 16'd952 : (ctrl[6:4]==3'd3) ? 16'd1480 : 16'd1856) :
                        (mode_w==2'd2) ? ((ctrl[6:4]==3'd2) ? 16'd606 : (ctrl[6:4]==3'd3) ? 16'd824  : 16'd1150) :
                                         16'd2;

    // ---------------- DUT 接口 ----------------
    reg         dut_rst, dut_start, dut_vin, dut_rout;
    wire [63:0] dut_din;               // 由 inbuf RAM 的 dob 直接驱动
    wire        dut_rin, dut_vout;     // DUT 的 ready_i(收数口,输出) / valid_o
    wire [63:0] dut_dout;

    combined_top u_dut (
        .clk     (PCLK),
        .rst     (dut_rst),
        .start   (dut_start),
        .mode    (ctrl[2:1]),        // 0=keygen 1=verify 2=sign
        .sec_lvl (ctrl[6:4]),
        .valid_i (dut_vin),
        .ready_i (dut_rin),          // DUT 输出
        .data_i  (dut_din),
        .valid_o (dut_vout),
        .ready_o (dut_rout),         // DUT 输入（出数口 ready，我们驱动）
        .data_o  (dut_dout)
    );

    // ---------------- 流式引擎 FSM ----------------
    localparam S_IDLE=3'd0, S_RST=3'd1, S_PULSE=3'd2, S_IN=3'd3,
               S_WAIT=3'd4, S_OUT=3'd5, S_DONE=3'd6;
    reg [2:0]  state;
    reg [15:0] ctr;
    reg [1:0]  rst_cnt;

    always @(posedge PCLK or negedge PRESETn) begin
        if (!PRESETn) begin
            state <= S_IDLE; ctr <= 0; busy <= 0; done <= 0; result <= 0;
            dut_rst <= 0; dut_start <= 0; dut_vin <= 0; dut_rout <= 0;
        end else begin
            dut_start <= 1'b0;
            if (wr && PADDR[7:0]==8'h04) done <= 1'b0;   // CPU 写 STATUS 清 done
            case (state)
            S_IDLE: if (ctrl[0]) begin
                        busy <= 1; done <= 1'b0; result <= 1'b0;
                        ctr <= 0; rst_cnt <= 0; dut_rst <= 1;
                        state <= S_RST;
                    end
            S_RST:  if (rst_cnt == 2'd1) begin
                        dut_rst <= 0; dut_start <= 1;      // start 打 1 拍
                        state <= S_PULSE;
                    end else rst_cnt <= rst_cnt + 1'b1;
            S_PULSE: begin
                        state <= S_IN;
                        dut_vin <= 1;                  // inbuf 读地址=ctr=0，下一拍 dob=word0
                    end
            S_IN:   if (dut_rin) begin
                        if (ctr == n_in - 1) begin
                            dut_vin <= 0; dut_rout <= 1; ctr <= 0;
                            state <= S_WAIT;
                        end else begin
                            ctr <= ctr + 1'b1;         // 读地址组合切到 ctr+1，下一拍 dob=下一字
                        end
                    end
            S_WAIT: if (dut_vout) begin                       // 收第 1 个 64b 结果字（outbuf 写在 RAM 块）
                        result <= dut_dout[0];                // verify: 1=拒绝
                        ctr <= 2;
                        if (n_out == 16'd2) state <= S_DONE;  // verify 只有 1 个 64b 字
                        else                state <= S_OUT;
                    end
            S_OUT:  if (dut_vout) begin                       // keygen/sign 多字输出（outbuf 写在 RAM 块）
                        if (ctr == n_out - 16'd2) state <= S_DONE;
                        else ctr <= ctr + 16'd2;
                    end
            S_DONE: begin busy <= 0; done <= 1; dut_rout <= 0; state <= S_IDLE; end
            default: state <= S_IDLE;
            endcase
        end
    end

    // ---------------- 输入/输出缓冲：双口 RAM（映射 Block RAM） ----------------
    wire inbuf_wr = wr && !busy && PADDR[7:0]==8'h14;
    wire [IN_AW-2:0] inbuf_rd_addr = (state == S_IN && dut_rin) ? ctr[IN_AW-2:0] + 1'b1
                                                                 : ctr[IN_AW-2:0];
    wire outbuf_we = (state == S_WAIT && dut_vout) || (state == S_OUT && dut_vout);
    wire [OUT_AW-2:0] outbuf_wr_addr = (state == S_WAIT) ? {(OUT_AW-1){1'b0}} : ctr[OUT_AW-1:1];

    assign dut_din = {inbuf_hi_dob, inbuf_lo_dob};

    dual_port_ram #(.WIDTH(32), .LENGTH(1<<(IN_AW-1))) u_inbuf_hi (
        .clka(PCLK), .clkb(PCLK), .ena(1'b1), .enb(1'b1),
        .wea(inbuf_wr & ~wptr[0]), .web(1'b0),
        .addra(wptr[IN_AW-1:1]), .addrb(inbuf_rd_addr),
        .dia(PWDATA), .dib(32'b0), .doa(), .dob(inbuf_hi_dob));

    dual_port_ram #(.WIDTH(32), .LENGTH(1<<(IN_AW-1))) u_inbuf_lo (
        .clka(PCLK), .clkb(PCLK), .ena(1'b1), .enb(1'b1),
        .wea(inbuf_wr & wptr[0]), .web(1'b0),
        .addra(wptr[IN_AW-1:1]), .addrb(inbuf_rd_addr),
        .dia(PWDATA), .dib(32'b0), .doa(), .dob(inbuf_lo_dob));

    dual_port_ram #(.WIDTH(32), .LENGTH(1<<(OUT_AW-1))) u_outbuf_hi (
        .clka(PCLK), .clkb(PCLK), .ena(1'b1), .enb(1'b1),
        .wea(outbuf_we), .web(1'b0),
        .addra(outbuf_wr_addr), .addrb(rptr[OUT_AW-1:1]),
        .dia(dut_dout[63:32]), .dib(32'b0), .doa(), .dob(outbuf_hi_dob));

    dual_port_ram #(.WIDTH(32), .LENGTH(1<<(OUT_AW-1))) u_outbuf_lo (
        .clka(PCLK), .clkb(PCLK), .ena(1'b1), .enb(1'b1),
        .wea(outbuf_we), .web(1'b0),
        .addra(outbuf_wr_addr), .addrb(rptr[OUT_AW-1:1]),
        .dia(dut_dout[31:0]), .dib(32'b0), .doa(), .dob(outbuf_lo_dob));

endmodule
