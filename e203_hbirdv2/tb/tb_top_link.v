
`include "e203_defines.v"

// =====================================================================
// tb_top_link.v — 文件信箱桥接 testbench（Python ↔ 常驻 xsim 实时驱动）
//
// 与 tb_top.v 相同的 DUT/时钟/复位/PUF 行为模型 hookup；去掉 SCEN/DEV
// 预编程序列，改为轮询文件信箱：
//   Python 写 D:/FPGA/sim_logs/bridge/cmd_<NNNN>.tmp 再改名 .req（原子）；
//   tb 轮询 cmd_<NNNN>.req（NNNN 从 0 递增），读出一行 ASCII 帧，
//   位bang 注入 UART0 RX（gpioA_drv[16]，div=15，位周期 64ns）并补 \r\n，
//   然后写空文件 cmd_<NNNN>.ack（Verilog 不能删文件，Python 见 ack 后删两者）。
//   特殊帧 QUIT → $finish。
//   UART0 TX 每个接收字节原始追加到 bridge/rsp.txt（保持打开 + 每行 fflush，
//   Python 按偏移增量读取）。全局空闲看门狗：IDLE_LIMIT_NS 仿真时间内无新
//   命令 → $finish，防僵尸仿真。
// 线上协议零改动（见 D:/FPGA/sim_logs/UART_PROTOCOL.md），本 tb 只是传输层。
// =====================================================================
module tb_top_link();

  reg  clk;
  reg  lfextclk;
  reg  rst_n;

  wire hfclk = clk;

  `define CPU_TOP u_e203_soc_top.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top
  `define EXU `CPU_TOP.u_e203_cpu.u_e203_core.u_e203_exu
  `define ITCM `CPU_TOP.u_e203_srams.u_e203_itcm_ram.u_e203_itcm_gnrl_ram.u_sirv_sim_ram

  wire [`E203_XLEN-1:0] x3 = `EXU.u_e203_exu_regfile.rf_r[3];
  wire [`E203_PC_SIZE-1:0] pc = `EXU.u_e203_exu_commit.alu_cmt_i_pc;

  reg [31:0] cycle_count;

  always @(posedge hfclk or negedge rst_n)
  begin
    if(rst_n == 1'b0) begin
        cycle_count <= 32'b0;
    end
    else begin
        cycle_count <= cycle_count + 1'b1;
    end
  end

  initial begin
    clk   <=0;
    lfextclk   <=0;
    rst_n <=0;
    #120 rst_n <=1;
  end

  always
  begin
     #2 clk <= ~clk;
  end

  always
  begin
     #33 lfextclk <= ~lfextclk;
  end

  integer i;

    reg [7:0] itcm_mem [0:(`E203_ITCM_RAM_DP*8)-1];
    initial begin
      $readmemh("test_link.verilog", itcm_mem);

      for (i=0;i<(`E203_ITCM_RAM_DP);i=i+1) begin
          `ITCM.mem_r[i][00+7:00] = itcm_mem[i*8+0];
          `ITCM.mem_r[i][08+7:08] = itcm_mem[i*8+1];
          `ITCM.mem_r[i][16+7:16] = itcm_mem[i*8+2];
          `ITCM.mem_r[i][24+7:24] = itcm_mem[i*8+3];
          `ITCM.mem_r[i][32+7:32] = itcm_mem[i*8+4];
          `ITCM.mem_r[i][40+7:40] = itcm_mem[i*8+5];
          `ITCM.mem_r[i][48+7:48] = itcm_mem[i*8+6];
          `ITCM.mem_r[i][56+7:56] = itcm_mem[i*8+7];
      end
    end


  wire jtag_TDI = 1'b0;
  wire jtag_TDO;
  wire jtag_TCK = 1'b0;
  wire jtag_TMS = 1'b0;
  wire jtag_TRST = 1'b0;

  wire jtag_DRV_TDO = 1'b0;


e203_soc_top u_e203_soc_top(

   .hfextclk(hfclk),
   .hfxoscen(),

   .lfextclk(lfextclk),
   .lfxoscen(),

   .io_pads_jtag_TCK_i_ival (jtag_TCK),
   .io_pads_jtag_TMS_i_ival (jtag_TMS),
   .io_pads_jtag_TDI_i_ival (jtag_TDI),
   .io_pads_jtag_TDO_o_oval (jtag_TDO),
   .io_pads_jtag_TDO_o_oe (),

   .io_pads_gpioA_i_ival(gpioA_drv),   // [16] = 串口B(UART0) RX，PC→FPGA 注入
   .io_pads_gpioA_o_oval(),
   .io_pads_gpioA_o_oe  (),

   .io_pads_gpioB_i_ival(gpioB_drv),   // [16] = 串口A(UART1) RX，PUF→E203 注入
   .io_pads_gpioB_o_oval(),
   .io_pads_gpioB_o_oe  (),

   .io_pads_qspi0_sck_o_oval (),
   .io_pads_qspi0_cs_0_o_oval(),
   .io_pads_qspi0_dq_0_i_ival(1'b1),
   .io_pads_qspi0_dq_0_o_oval(),
   .io_pads_qspi0_dq_0_o_oe  (),
   .io_pads_qspi0_dq_1_i_ival(1'b1),
   .io_pads_qspi0_dq_1_o_oval(),
   .io_pads_qspi0_dq_1_o_oe  (),
   .io_pads_qspi0_dq_2_i_ival(1'b1),
   .io_pads_qspi0_dq_2_o_oval(),
   .io_pads_qspi0_dq_2_o_oe  (),
   .io_pads_qspi0_dq_3_i_ival(1'b1),
   .io_pads_qspi0_dq_3_o_oval(),
   .io_pads_qspi0_dq_3_o_oe  (),

   .io_pads_aon_erst_n_i_ival (rst_n),//This is the real reset, active low
   .io_pads_aon_pmu_dwakeup_n_i_ival (1'b1),

   .io_pads_aon_pmu_vddpaden_o_oval (),
    .io_pads_aon_pmu_padrst_o_oval    (),

    .io_pads_bootrom_n_i_ival       (1'b0),// In Simulation we boot from ROM
    .io_pads_dbgmode0_n_i_ival       (1'b1),
    .io_pads_dbgmode1_n_i_ival       (1'b1),
    .io_pads_dbgmode2_n_i_ival       (1'b1)
);

// =====================================================================
// PUF 行为模型 + 双串口通道（与 tb_top.v 一致；DEV 固定 0，DEVICE_CONST=0xA5×32）
// =====================================================================
`include "D:/FPGA/e203_hbirdv2-master/tb/shake256_model.v"

localparam UART_BIT_NS = 64;             // 16 clk/bit @ 250MHz(4ns), div=15

reg [31:0] gpioA_drv = 32'hFFFF_FFFF;    // UART RX 空闲高电平
reg [31:0] gpioB_drv = 32'hFFFF_FFFF;

`define UART0_TX u_e203_soc_top.u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_perips.uart0_txd
`define UART1_TX u_e203_soc_top.u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_perips.uart1_txd

function [3:0] hexval;
  input [7:0] c;
  begin
    if (c >= "0" && c <= "9") hexval = c - "0";
    else if (c >= "a" && c <= "f") hexval = c - "a" + 10;
    else if (c >= "A" && c <= "F") hexval = c - "A" + 10;
    else hexval = 0;
  end
endfunction

function [7:0] to_hex;
  input [3:0] n;
  begin to_hex = (n < 10) ? ("0" + n) : ("a" + (n - 10)); end
endfunction

// ---------------- 串口 B：PC→FPGA 发送（位bang 到 gpioA_drv[16]） ----------------
task pc_send_byte;
  input [7:0] b;
  integer k;
  begin
    gpioA_drv[16] = 1'b0;  #(UART_BIT_NS);               // start
    for (k = 0; k < 8; k = k + 1) begin
      gpioA_drv[16] = b[k];  #(UART_BIT_NS);
    end
    gpioA_drv[16] = 1'b1;  #(UART_BIT_NS + UART_BIT_NS/2); // stop + 间隙
  end
endtask

// ---------------- 串口 B：FPGA→PC 接收（uart0_txd → rsp.txt + [FPGA] 行打印） ----------------
reg [7:0] fpga_line [0:4991];
integer   fpga_llen = 0;
reg       rx0_busy = 0;
reg [7:0] rx0_byte;
integer   b0;
integer   rsp_fd = 0;
integer   eval_i;

task fpga_handle_byte;
  input [7:0] ch;
  integer pi;
  begin
    if (rsp_fd != 0) begin
      $fwrite(rsp_fd, "%c", ch);         // 原始字节追加（xsim Windows 文本模式 \n→\r\n，Python 侧兼容）
    end
    if (ch == 8'h0A) begin
      if (rsp_fd != 0) $fflush(rsp_fd);  // 行边界落盘，Python 增量可见
      $write("[%0t] [FPGA] ", $time);
      for (pi = 0; pi < fpga_llen; pi = pi + 1) $write("%c", fpga_line[pi]);
      $display("");
      fpga_llen = 0;
    end else if (ch != 8'h0D) begin
      if (fpga_llen < 4992) begin
        fpga_line[fpga_llen] = ch;
        fpga_llen = fpga_llen + 1;
      end
    end
  end
endtask

always @(negedge `UART0_TX) begin
  if (!rx0_busy && rst_n) begin
    rx0_busy = 1;
    #(UART_BIT_NS/2);                    // 起始位中点：先确认不是毛刺
    if (`UART0_TX === 1'b0) begin
      #(UART_BIT_NS);                    // → bit0 中点
      for (b0 = 0; b0 < 8; b0 = b0 + 1) begin
        rx0_byte[b0] = `UART0_TX;
        #(UART_BIT_NS);
      end
      if (`UART0_TX === 1'b1)            // 停止位校验，防假触发
        fpga_handle_byte(rx0_byte);
    end
    rx0_busy = 0;
  end
end

// ---------------- 串口 B 线上行解码：PC→FPGA 实际波形（gpioA_drv[16]） ----------------
reg [7:0] pc_line [0:4991];
integer   pc_llen = 0;
reg       pcrx_busy = 0;
reg [7:0] pcrx_byte;
integer   pb0;

always @(negedge gpioA_drv[16]) begin
  if (!pcrx_busy && rst_n) begin : pcrx_blk
    integer pi;
    pcrx_busy = 1;
    #(UART_BIT_NS/2);
    if (gpioA_drv[16] === 1'b0) begin
      #(UART_BIT_NS);
      for (pb0 = 0; pb0 < 8; pb0 = pb0 + 1) begin
        pcrx_byte[pb0] = gpioA_drv[16];
        #(UART_BIT_NS);
      end
      if (gpioA_drv[16] === 1'b1) begin
        if (pcrx_byte == 8'h0A) begin
          $write("[%0t] [PC>] ", $time);
          for (pi = 0; pi < pc_llen; pi = pi + 1) $write("%c", pc_line[pi]);
          $display("");
          pc_llen = 0;
        end else if (pcrx_byte != 8'h0D) begin
          if (pc_llen < 4991) begin
            pc_line[pc_llen] = pcrx_byte;
            pc_llen = pc_llen + 1;
          end
        end
      end
    end
    pcrx_busy = 0;
  end
end

// ---------------- 串口 A 线上行解码：PUF→E203 实际波形（gpioB_drv[16]） ----------------
reg [7:0] pa_line [0:255];
integer   pa_llen = 0;
reg       parx_busy = 0;
reg [7:0] parx_byte;
integer   pa0;

always @(negedge gpioB_drv[16]) begin
  if (!parx_busy && rst_n) begin : parx_blk
    integer pi;
    parx_busy = 1;
    #(UART_BIT_NS/2);
    if (gpioB_drv[16] === 1'b0) begin
      #(UART_BIT_NS);
      for (pa0 = 0; pa0 < 8; pa0 = pa0 + 1) begin
        parx_byte[pa0] = gpioB_drv[16];
        #(UART_BIT_NS);
      end
      if (gpioB_drv[16] === 1'b1) begin
        if (parx_byte == 8'h0A) begin
          $write("[%0t] [PUF>] ", $time);
          for (pi = 0; pi < pa_llen; pi = pi + 1) $write("%c", pa_line[pi]);
          $display("");
          pa_llen = 0;
        end else if (parx_byte != 8'h0D) begin
          if (pa_llen < 255) begin
            pa_line[pa_llen] = parx_byte;
            pa_llen = pa_llen + 1;
          end
        end
      end
    end
    parx_busy = 0;
  end
end

// ---------------- 串口 A：PUF 行为模型（收 uart1_txd 的 CHAL，回注 R） ----------------
integer   dev_sel = 0;                   // 桥接模式固定 DEV=0
reg [255:0] dev_const = {32{8'hA5}};     // DEVICE_CONST：设备指纹

reg [7:0] puf_line [0:127];
integer   puf_llen = 0;
reg       puf_busy = 0;
reg [7:0] rx1_byte;
integer   b1;
reg [8*160-1:0] puf_msg;
integer   puf_k, puf_rep;

task puf_send_byte;
  input [7:0] b;
  integer k;
  begin
    gpioB_drv[16] = 1'b0;  #(UART_BIT_NS);
    for (k = 0; k < 8; k = k + 1) begin
      gpioB_drv[16] = b[k];  #(UART_BIT_NS);
    end
    gpioB_drv[16] = 1'b1;  #(UART_BIT_NS + UART_BIT_NS/2);
  end
endtask

task puf_handle_line;
  reg [255:0] cc, rr;
  reg [7:0]   by;
  integer k;
  begin
    if (puf_llen >= 69 && puf_line[0]=="C" && puf_line[1]=="H" && puf_line[2]=="A" &&
        puf_line[3]=="L" && puf_line[4]==" ") begin
      for (k = 0; k < 32; k = k + 1) begin
        by = {hexval(puf_line[5+2*k]), hexval(puf_line[6+2*k])};
        cc[255-8*k -: 8] = by;
      end
      $display("[%0t] [PUF] recv C=%h", $time, cc);
      puf_msg = {160*8{1'b0}};
      puf_msg[8*160-1 -: 256] = cc;
      puf_msg[8*128-1 -: 256] = dev_const;
      shake256(puf_msg, 64, rr);          // R = SHAKE-256(C || DEVICE_CONST)
      $display("[%0t] [PUF] R=SHAKE256(C||DEVICE_CONST)=%h", $time, rr);
      puf_send_byte(8'h0D); puf_send_byte(8'h0A);   // 前导空行×4（吸收 UART1 首帧幻影）
      puf_send_byte(8'h0D); puf_send_byte(8'h0A);
      puf_send_byte(8'h0D); puf_send_byte(8'h0A);
      puf_send_byte(8'h0D); puf_send_byte(8'h0A);
      #20000;
      for (puf_rep = 0; puf_rep < 3; puf_rep = puf_rep + 1) begin
        puf_send_byte("R"); puf_send_byte(" ");
        for (k = 0; k < 32; k = k + 1) begin
          puf_send_byte(to_hex(rr[255-8*k   -: 4]));
          puf_send_byte(to_hex(rr[255-8*k-4 -: 4]));
        end
        puf_send_byte(8'h0D); puf_send_byte(8'h0A);
        #300000;                     // 重复 3 次，跨越首帧异常/耳聋期
      end
    end
  end
endtask

always @(negedge `UART1_TX) begin
  if (!puf_busy && rst_n) begin
    puf_busy = 1;
    #(UART_BIT_NS/2);
    if (`UART1_TX === 1'b0) begin
      #(UART_BIT_NS);
      for (b1 = 0; b1 < 8; b1 = b1 + 1) begin
        rx1_byte[b1] = `UART1_TX;
        #(UART_BIT_NS);
      end
      if (`UART1_TX === 1'b1) begin
        if (rx1_byte == 8'h0A) begin
          puf_handle_line;
          puf_llen = 0;
        end else if (rx1_byte != 8'h0D) begin
          if (puf_llen < 128) begin
            puf_line[puf_llen] = rx1_byte;
            puf_llen = puf_llen + 1;
          end
        end
      end
    end
    puf_busy = 0;
  end
end

// =====================================================================
// 文件信箱命令循环（Python ↔ tb）
//   req: bridge/cmd_<NNNN>.req  一行 ASCII 帧（容忍 \r\n / \n）
//   ack: bridge/cmd_<NNNN>.ack  空文件，表示该帧已完整注入 UART0
//   QUIT → 写 ack 后 $finish；空闲超过 IDLE_LIMIT_NS → $finish
// 注意：Verilog 字符串字面量 "\r" 在 xsim 中会退化为 'r'，故 CRLF 一律用 8'h0D/8'h0A
// =====================================================================
localparam POLL_NS       = 50000;                // 轮询间隔 50µs sim（拾取延迟 ≈ 4s wall；
                                                 // 实测仿真速率 ~7-12µs sim/s wall，fopen 轮询开销可忽略）
localparam [63:0] IDLE_LIMIT_NS = 64'd100_000_000;  // 100ms sim 无新命令自终止（≈2-3h wall，
                                                 // >6× 最长命令间隔 FW≈15ms sim），防僵尸仿真
localparam MAX_FRAME     = 8192;               // 最长帧 VER 4848hex + 余量

reg  [8*256:1] req_name;
reg  [8*256:1] ack_name;
reg  [7:0]     cbuf [0:MAX_FRAME-1];
integer        cmd_id = 0;
integer        cmd_fd, ack_fd, rc, cpos, k;
time           last_cmd_time = 0;

initial begin
  rsp_fd = $fopen("D:/FPGA/sim_logs/bridge/rsp.txt", "w");   // 截断重建；保持打开
  if (rsp_fd == 0) begin
    $display("[LINK] FATAL: cannot open rsp.txt for write");
    $finish;
  end
  $display("[LINK] tb_top_link up; mailbox=D:/FPGA/sim_logs/bridge/ poll=%0dns idle_limit=%0dns",
           POLL_NS, IDLE_LIMIT_NS);
end

// 空闲看门狗：last_cmd_time 在每条命令消费后刷新
initial begin
  wait (rst_n === 1'b1);
  forever begin
    #1000000;                                    // 1ms 检查一次
    if (($time - last_cmd_time) > IDLE_LIMIT_NS) begin
      $display("[%0t] [LINK] idle watchdog (%0dns no command) -> $finish", $time, IDLE_LIMIT_NS);
      $finish;
    end
  end
end

initial begin : link_loop
  wait (rst_n === 1'b1);
  #1000;
  forever begin
    $sformat(req_name, "D:/FPGA/sim_logs/bridge/cmd_%04d.req", cmd_id);
    cmd_fd = $fopen(req_name, "r");
    if (cmd_fd == 0) begin
      #(POLL_NS);                                // 无新命令，下一拍再查
    end else begin
      // 读一行（容忍 \r\n / 纯 \n；EOF 或 \n 结束）
      cpos = 0;
      rc = $fgetc(cmd_fd);
      while ((rc != -1) && (rc != 10) && (cpos < MAX_FRAME)) begin
        if (rc != 13) begin
          cbuf[cpos] = rc[7:0];
          cpos = cpos + 1;
        end
        rc = $fgetc(cmd_fd);
      end
      $fclose(cmd_fd);                           // 立即关闭，Python 随后删除
      last_cmd_time = $time;

      $write("[%0t] [LINK] cmd %04d (%0dB): ", $time, cmd_id, cpos);
      for (k = 0; (k < cpos) && (k < 24); k = k + 1) $write("%c", cbuf[k]);
      if (cpos > 24) $write("...");
      $display("");

      if ((cpos >= 4) && (cbuf[0]=="Q") && (cbuf[1]=="U") && (cbuf[2]=="I") && (cbuf[3]=="T")) begin
        $sformat(ack_name, "D:/FPGA/sim_logs/bridge/cmd_%04d.ack", cmd_id);
        ack_fd = $fopen(ack_name, "w");
        if (ack_fd != 0) $fclose(ack_fd);
        $display("[%0t] [LINK] QUIT received -> $finish", $time);
        #1000;
        $finish;
      end else begin
        if (cpos == 0) begin
          $display("[%0t] [LINK] WARN: empty frame, ack without inject", $time);
        end else begin
          $display("[%0t] [LINK] cmd %04d injecting %0d bytes...", $time, cmd_id, cpos + 2);
          for (k = 0; k < cpos; k = k + 1) pc_send_byte(cbuf[k]);
          pc_send_byte(8'h0D); pc_send_byte(8'h0A);
          $display("[%0t] [LINK] cmd %04d injection done", $time, cmd_id);
        end
        $sformat(ack_name, "D:/FPGA/sim_logs/bridge/cmd_%04d.ack", cmd_id);
        ack_fd = $fopen(ack_name, "w");
        if (ack_fd != 0) $fclose(ack_fd);
        cmd_id = cmd_id + 1;
      end
    end
  end
end

endmodule
