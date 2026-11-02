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
    reg [31:0] inbuf  [0:(1<<IN_AW)-1];
    reg [31:0] outbuf [0:(1<<OUT_AW)-1];

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
                8'h14: begin inbuf[wptr] <= PWDATA; wptr <= wptr + 1'b1; end
                8'h18: rptr <= PWDATA[OUT_AW-1:0];
            endcase
            else if (ctrl[0]) ctrl[0] <= 1'b0;
            if (wr && PADDR[7:0]==8'h04) done <= 1'b0;
        end
    end

    always @(posedge PCLK) begin
        if (rd) case (PADDR[7:0])
            8'h00: PRDATA <= ctrl;
            8'h04: PRDATA <= {29'b0, result, done, busy};
            8'h08: PRDATA <= mlen;
            8'h1C: begin PRDATA <= outbuf[rptr]; rptr <= rptr + 1'b1; end
            default: PRDATA <= 32'h0;
        endcase
    end

    assign irq_o = ien[0] & done;

    // ---------------- 字数表（verify 定稿；keygen/sign 从对应 tb 的 LOAD 状态抄）----------------
    wire [15:0] n_z  = (ctrl[6:4]==3'd2) ? 16'd288 : (ctrl[6:4]==3'd3) ? 16'd400 : 16'd560;
    wire [15:0] n_t1 = (ctrl[6:4]==3'd2) ? 16'd160 : (ctrl[6:4]==3'd3) ? 16'd240 : 16'd320;
    wire [15:0] n_h  = (ctrl[6:4]==3'd2) ? 16'd11  : (ctrl[6:4]==3'd3) ? 16'd8   : 16'd11;
    wire [15:0] n_m  = ({6'b0, mlen[15:0]} + 16'd7) >> 3;  // ceil(mlen/8)
    wire [15:0] n_in = 16'd4 + 16'd4 + n_z + n_t1 + 16'd1 + n_m + n_h;
    wire [15:0] n_out = 16'd1;   // verify: 1 字；keygen/sign 待补

    // ---------------- DUT 接口 ----------------
    reg         dut_rst, dut_start, dut_vin, dut_rout;
    reg  [63:0] dut_din;
    wire        dut_rin, dut_vout;   // DUT 的 ready_i(收数口,输出) / valid_o
    wire [63:0] dut_dout;

    combined_top u_dut (
        .clk     (PCLK),
        .rst     (dut_rst),
        .start   (dut_start),
        .mode    (ctrl[2:1]),        // verify=1
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
                        dut_vin <= 1; dut_din <= {inbuf[0], inbuf[1]};
                    end
            S_IN:   if (dut_rin) begin
                        if (ctr == n_in - 1) begin
                            dut_vin <= 0; dut_rout <= 1; ctr <= 0;
                            state <= S_WAIT;
                        end else begin
                            ctr <= ctr + 1'b1;
                            dut_din <= {inbuf[(ctr+1)*2], inbuf[(ctr+1)*2+1]};
                        end
                    end
            S_WAIT: if (dut_vout) begin                       // 收第 1 个结果字
                        result  <= dut_dout[0];
                        outbuf[0] <= dut_dout[31:0];
                        ctr <= 1;
                        if (n_out == 1) state <= S_DONE;      // verify 只有 1 字
                        else            state <= S_OUT;
                    end
            S_OUT:  if (dut_vout) begin                       // keygen/sign 多字输出
                        outbuf[ctr] <= dut_dout[31:0];
                        if (ctr == n_out - 1) state <= S_DONE;
                        else ctr <= ctr + 1'b1;
                    end
            S_DONE: begin busy <= 0; done <= 1; dut_rout <= 0; state <= S_IDLE; end
            default: state <= S_IDLE;
            endcase
        end
    end

endmodule