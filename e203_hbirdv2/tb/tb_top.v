
`include "e203_defines.v"

module tb_top();

  reg  clk;
  reg  lfextclk;
  reg  rst_n;

  wire hfclk = clk;

  `define CPU_TOP u_e203_soc_top.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top
  `define EXU `CPU_TOP.u_e203_cpu.u_e203_core.u_e203_exu
  `define ITCM `CPU_TOP.u_e203_srams.u_e203_itcm_ram.u_e203_itcm_gnrl_ram.u_sirv_sim_ram

  `define PC_WRITE_TOHOST       `E203_PC_SIZE'h80000086
  `define PC_EXT_IRQ_BEFOR_MRET `E203_PC_SIZE'h800000a6
  `define PC_SFT_IRQ_BEFOR_MRET `E203_PC_SIZE'h800000be
  `define PC_TMR_IRQ_BEFOR_MRET `E203_PC_SIZE'h800000d6
  `define PC_AFTER_SETMTVEC     `E203_PC_SIZE'h8000015C

  wire [`E203_XLEN-1:0] x3 = `EXU.u_e203_exu_regfile.rf_r[3];
  wire [`E203_PC_SIZE-1:0] pc = `EXU.u_e203_exu_commit.alu_cmt_i_pc;
  wire [`E203_PC_SIZE-1:0] pc_vld = `EXU.u_e203_exu_commit.alu_cmt_i_valid;

  reg [31:0] pc_write_to_host_cnt;
  reg [31:0] pc_write_to_host_cycle;
  reg [31:0] valid_ir_cycle;
  reg [31:0] cycle_count;
  reg pc_write_to_host_flag;

  always @(posedge hfclk or negedge rst_n)
  begin 
    if(rst_n == 1'b0) begin
        pc_write_to_host_cnt <= 32'b0;
        pc_write_to_host_flag <= 1'b0;
        pc_write_to_host_cycle <= 32'b0;
    end
    else if (pc_vld & (pc == `PC_WRITE_TOHOST)) begin
        pc_write_to_host_cnt <= pc_write_to_host_cnt + 1'b1;
        pc_write_to_host_flag <= 1'b1;
        if (pc_write_to_host_flag == 1'b0) begin
            pc_write_to_host_cycle <= cycle_count;
        end
    end
  end

  always @(posedge hfclk or negedge rst_n)
  begin 
    if(rst_n == 1'b0) begin
        cycle_count <= 32'b0;
    end
    else begin
        cycle_count <= cycle_count + 1'b1;
    end
  end

  wire i_valid = `EXU.i_valid;
  wire i_ready = `EXU.i_ready;

  always @(posedge hfclk or negedge rst_n)
  begin 
    if(rst_n == 1'b0) begin
        valid_ir_cycle <= 32'b0;
    end
    else if(i_valid & i_ready & (pc_write_to_host_flag == 1'b0)) begin
        valid_ir_cycle <= valid_ir_cycle + 1'b1;
    end
  end


  // Randomly force the external interrupt
  `define EXT_IRQ u_e203_soc_top.u_e203_subsys_top.u_e203_subsys_main.plic_ext_irq
  `define SFT_IRQ u_e203_soc_top.u_e203_subsys_top.u_e203_subsys_main.clint_sft_irq
  `define TMR_IRQ u_e203_soc_top.u_e203_subsys_top.u_e203_subsys_main.clint_tmr_irq

  `define U_CPU u_e203_soc_top.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top.u_e203_cpu
  `define ITCM_BUS_ERR `U_CPU.u_e203_itcm_ctrl.sram_icb_rsp_err
  `define ITCM_BUS_READ `U_CPU.u_e203_itcm_ctrl.sram_icb_rsp_read
  `define STATUS_MIE   `U_CPU.u_e203_core.u_e203_exu.u_e203_exu_commit.u_e203_exu_excp.status_mie_r

  wire stop_assert_irq = (pc_write_to_host_cnt > 32);

  reg tb_itcm_bus_err;

  reg tb_ext_irq;
  reg tb_tmr_irq;
  reg tb_sft_irq;
  initial begin
    tb_ext_irq = 1'b0;
    tb_tmr_irq = 1'b0;
    tb_sft_irq = 1'b0;
  end

`ifdef ENABLE_TB_FORCE
  initial begin
    tb_itcm_bus_err = 1'b0;
    #100
    @(pc == `PC_AFTER_SETMTVEC ) // Wait the program goes out the reset_vector program
    forever begin
      repeat ($urandom_range(1, 20)) @(posedge clk) tb_itcm_bus_err = 1'b0; // Wait random times
      repeat ($urandom_range(1, 200)) @(posedge clk) tb_itcm_bus_err = 1'b1; // Wait random times
      if(stop_assert_irq) begin
          break;
      end
    end
  end


  initial begin
    force `EXT_IRQ = tb_ext_irq;
    force `SFT_IRQ = tb_sft_irq;
    force `TMR_IRQ = tb_tmr_irq;
       // We force the bus-error only when:
       //   It is in common code, not in exception code, by checking MIE bit
       //   It is in read operation, not write, otherwise the test cannot recover
    force `ITCM_BUS_ERR = tb_itcm_bus_err
                        & `STATUS_MIE 
                        & `ITCM_BUS_READ
                        ;
  end


  initial begin
    #100
    @(pc == `PC_AFTER_SETMTVEC ) // Wait the program goes out the reset_vector program
    forever begin
      repeat ($urandom_range(1, 1000)) @(posedge clk) tb_ext_irq = 1'b0; // Wait random times
      tb_ext_irq = 1'b1; // assert the irq
      @((pc == `PC_EXT_IRQ_BEFOR_MRET)) // Wait the program run into the IRQ handler by check PC values
      tb_ext_irq = 1'b0;
      if(stop_assert_irq) begin
          break;
      end
    end
  end

  initial begin
    #100
    @(pc == `PC_AFTER_SETMTVEC ) // Wait the program goes out the reset_vector program
    forever begin
      repeat ($urandom_range(1, 1000)) @(posedge clk) tb_sft_irq = 1'b0; // Wait random times
      tb_sft_irq = 1'b1; // assert the irq
      @((pc == `PC_SFT_IRQ_BEFOR_MRET)) // Wait the program run into the IRQ handler by check PC values
      tb_sft_irq = 1'b0;
      if(stop_assert_irq) begin
          break;
      end
    end
  end

  initial begin
    #100
    @(pc == `PC_AFTER_SETMTVEC ) // Wait the program goes out the reset_vector program
    forever begin
      repeat ($urandom_range(1, 1000)) @(posedge clk) tb_tmr_irq = 1'b0; // Wait random times
      tb_tmr_irq = 1'b1; // assert the irq
      @((pc == `PC_TMR_IRQ_BEFOR_MRET)) // Wait the program run into the IRQ handler by check PC values
      tb_tmr_irq = 1'b0;
      if(stop_assert_irq) begin
          break;
      end
    end
  end
`endif

  reg[8*300:1] testcase;
  integer dumpwave;

  initial begin
    $display("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!");  
    if($value$plusargs("TESTCASE=%s",testcase))begin
      $display("TESTCASE=%s",testcase);
    end

    pc_write_to_host_flag <=0;
    clk   <=0;
    lfextclk   <=0;
    rst_n <=0;
    #120 rst_n <=1;

    wait (x3 == 32'd1); #10 rst_n <=1;
`ifdef ENABLE_TB_FORCE
    @((~tb_tmr_irq) & (~tb_sft_irq) & (~tb_ext_irq)) #10 rst_n <=1;// Wait the interrupt to complete
`endif

        $display("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~~~~~ Test Result Summary ~~~~~~~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~");
        $display("~TESTCASE: %s ~~~~~~~~~~~~~", testcase);
        $display("~~~~~~~~~~~~~~Total cycle_count value: %d ~~~~~~~~~~~~~", cycle_count);
        $display("~~~~~~~~~~The valid Instruction Count: %d ~~~~~~~~~~~~~", valid_ir_cycle);
        $display("~~~~~The test ending reached at cycle: %d ~~~~~~~~~~~~~", pc_write_to_host_cycle);
        $display("~~~~~~~~~~~~~~~The final x3 Reg value: %d ~~~~~~~~~~~~~", x3);
        $display("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~");
    if (x3 == 1) begin
        $display("~~~~~~~~~~~~~~~~ TEST_PASS ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~ #####     ##     ####    #### ~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~ #    #   #  #   #       #     ~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~ #    #  #    #   ####    #### ~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~ #####   ######       #       #~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~ #       #    #  #    #  #    #~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~ #       #    #   ####    #### ~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~");
    end
    else begin
        $display("~~~~~~~~~~~~~~~~ TEST_FAIL ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~~######    ##       #    #     ~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~~#        #  #      #    #     ~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~~#####   #    #     #    #     ~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~~#       ######     #    #     ~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~~#       #    #     #    #     ~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~~#       #    #     #    ######~~~~~~~~~~~~~~~~");
        $display("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~");
    end
    #10
     $finish;
  end

  initial begin
    #400000000        // 演示场景最长 ~30ms sim，超时放宽到 400ms
        $display("Time Out !!!");
     $finish;
  end

  always
  begin 
     #2 clk <= ~clk;
  end

  always
  begin 
     #33 lfextclk <= ~lfextclk;
  end



  
  
  initial begin
    if($value$plusargs("DUMPWAVE=%d",dumpwave)) begin
      if(dumpwave != 0) begin

	 `ifdef vcs
            $display("VCS used");
            $fsdbDumpfile("tb_top.fsdb");
            $fsdbDumpvars(0, tb_top, "+mda");
         `endif

	 `ifdef iverilog
            $display("iverlog used");
	    $dumpfile("tb_top.vcd");
            $dumpvars(0, tb_top);
         `endif
      end
    end
  end




  integer i;

    reg [7:0] itcm_mem [0:(`E203_ITCM_RAM_DP*8)-1];
    initial begin
      $readmemh("test.verilog", itcm_mem);

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

        $display("ITCM 0x00: %h", `ITCM.mem_r[8'h00]);
        $display("ITCM 0x01: %h", `ITCM.mem_r[8'h01]);
        $display("ITCM 0x02: %h", `ITCM.mem_r[8'h02]);
        $display("ITCM 0x03: %h", `ITCM.mem_r[8'h03]);
        $display("ITCM 0x04: %h", `ITCM.mem_r[8'h04]);
        $display("ITCM 0x05: %h", `ITCM.mem_r[8'h05]);
        $display("ITCM 0x06: %h", `ITCM.mem_r[8'h06]);
        $display("ITCM 0x07: %h", `ITCM.mem_r[8'h07]);
        $display("ITCM 0x16: %h", `ITCM.mem_r[8'h16]);
        $display("ITCM 0x20: %h", `ITCM.mem_r[8'h20]);

    end 



  wire jtag_TDI = 1'b0;
  wire jtag_TDO;
  wire jtag_TCK = 1'b0;
  wire jtag_TMS = 1'b0;
  wire jtag_TRST = 1'b0;

  wire jtag_DRV_TDO = 1'b0;


  // ============ Dilithium 调试探针（仅 $display，不改逻辑） ============
  // 默认关闭（提速+日志干净），调试时 +define+DIL_DEBUG_PROBE 打开
`ifdef DIL_DEBUG_PROBE
  `define DAPB u_e203_soc_top.u_dilithium_apb

  reg [31:0] apb_wr_cnt, apb_rd_cnt;
  reg [11:0] last_wptr;
  reg        last_busy, last_done;
  reg [2:0]  last_state;
  reg [31:0] last_x3;

  initial begin
    apb_wr_cnt = 0; apb_rd_cnt = 0; last_wptr = 0;
    last_busy = 0; last_done = 0; last_state = 0; last_x3 = 0;
  end

  // APB 事务计数 + CTRL/WDATA 关键写
  always @(posedge `DAPB.PCLK) begin
    if (`DAPB.PSEL & `DAPB.PENABLE & `DAPB.PWRITE) begin
      apb_wr_cnt <= apb_wr_cnt + 1;
      if (`DAPB.PADDR[7:0] == 8'h00)
        $display("[%0t] DIL_PROBE: CTRL write = %h (wptr=%0d, apb_wr=%0d)", $time, `DAPB.PWDATA, `DAPB.wptr, apb_wr_cnt);
      if (`DAPB.PADDR[7:0] == 8'h10)
        $display("[%0t] DIL_PROBE: PTR write = %h", $time, `DAPB.PWDATA);
      if ((`DAPB.PADDR[7:0] == 8'h14) && (`DAPB.wptr == 0))
        $display("[%0t] DIL_PROBE: first WDATA = %h", $time, `DAPB.PWDATA);
    end
    if (`DAPB.PSEL & `DAPB.PENABLE & ~`DAPB.PWRITE) begin
      apb_rd_cnt <= apb_rd_cnt + 1;
      if ((`DAPB.PADDR[7:0] == 8'h04) && (apb_rd_cnt < 5))
        $display("[%0t] DIL_PROBE: STATUS read", $time);
    end
  end

  // wptr 里程碑
  always @(posedge `DAPB.PCLK) begin
    if (`DAPB.wptr != last_wptr) begin
      if ((`DAPB.wptr == 12'd1) || (`DAPB.wptr % 256 == 0))
        $display("[%0t] DIL_PROBE: wptr=%0d", $time, `DAPB.wptr);
      last_wptr <= `DAPB.wptr;
    end
  end

  // busy/done/state 跳变
  always @(posedge `DAPB.PCLK) begin
    if (`DAPB.busy !== last_busy) begin
      $display("[%0t] DIL_PROBE: busy -> %b (wptr=%0d, apb_wr=%0d)", $time, `DAPB.busy, `DAPB.wptr, apb_wr_cnt);
      last_busy <= `DAPB.busy;
    end
    if (`DAPB.done !== last_done) begin
      $display("[%0t] DIL_PROBE: done -> %b result=%b", $time, `DAPB.done, `DAPB.result);
      if (`DAPB.done && `DAPB.ctrl[2:1] == 2'd0) begin
        $display("[%0t] DIL_PROBE: KG outbuf[0..7]  = %h %h %h %h %h %h %h %h", $time,
                 `DAPB.u_outbuf_hi.ram[0], `DAPB.u_outbuf_lo.ram[0], `DAPB.u_outbuf_hi.ram[1], `DAPB.u_outbuf_lo.ram[1],
                 `DAPB.u_outbuf_hi.ram[2], `DAPB.u_outbuf_lo.ram[2], `DAPB.u_outbuf_hi.ram[3], `DAPB.u_outbuf_lo.ram[3]);
        $display("[%0t] DIL_PROBE: KG outbuf[8..15] = %h %h %h %h %h %h %h %h", $time,
                 `DAPB.u_outbuf_hi.ram[4], `DAPB.u_outbuf_lo.ram[4], `DAPB.u_outbuf_hi.ram[5], `DAPB.u_outbuf_lo.ram[5],
                 `DAPB.u_outbuf_hi.ram[6], `DAPB.u_outbuf_lo.ram[6], `DAPB.u_outbuf_hi.ram[7], `DAPB.u_outbuf_lo.ram[7]);
        $display("[%0t] DIL_PROBE: KG inbuf[0..7]   = %h %h %h %h %h %h %h %h", $time,
                 `DAPB.u_inbuf_hi.ram[0], `DAPB.u_inbuf_lo.ram[0], `DAPB.u_inbuf_hi.ram[1], `DAPB.u_inbuf_lo.ram[1],
                 `DAPB.u_inbuf_hi.ram[2], `DAPB.u_inbuf_lo.ram[2], `DAPB.u_inbuf_hi.ram[3], `DAPB.u_inbuf_lo.ram[3]);
      end
      last_done <= `DAPB.done;
    end
    if (`DAPB.state !== last_state) begin
      $display("[%0t] DIL_PROBE: state %0d -> %0d (ctr=%0d)", $time, last_state, `DAPB.state, `DAPB.ctr);
      last_state <= `DAPB.state;
    end
  end

  // gp(x3) 变化
  always @(x3) begin
    if (x3 !== last_x3) begin
      $display("[%0t] DIL_PROBE: x3(gp) = %h", $time, x3);
      last_x3 <= x3;
    end
  end

  // 心跳：每 2ms 打一次全局状态
  initial begin
    forever begin
      #2000000;
      $display("[%0t] DIL_PROBE: HEARTBEAT state=%0d busy=%b done=%b wptr=%0d ctr=%0d apb_wr=%0d apb_rd=%0d pc=%h x3=%h",
               $time, `DAPB.state, `DAPB.busy, `DAPB.done, `DAPB.wptr, `DAPB.ctr, apb_wr_cnt, apb_rd_cnt, pc, x3);
    end
  end

  // ============ 核 FSM0 / GenY / keccak[2] 探针（仅 $display） ============
  reg [4:0] last_fsm0;
  reg [3:0] last_geny;
  initial begin last_fsm0 = 0; last_geny = 0; end

  always @(posedge `DAPB.PCLK) begin
    if (`DAPB.u_dut.cstate0 !== last_fsm0) begin
      $display("[%0t] DIL_PROBE: FSM0 %0d -> %0d (mode=%0d ctr1=%0d)",
               $time, last_fsm0, `DAPB.u_dut.cstate0, `DAPB.u_dut.mode, `DAPB.u_dut.ctr1);
      last_fsm0 <= `DAPB.u_dut.cstate0;
    end
    if (`DAPB.u_dut.GEN_Y.cstate !== last_geny) begin
      $display("[%0t] DIL_PROBE: GENY %0d -> %0d (ctr=%0d)",
               $time, last_geny, `DAPB.u_dut.GEN_Y.cstate, `DAPB.u_dut.GEN_Y.ctr);
      last_geny <= `DAPB.u_dut.GEN_Y.cstate;
    end
  end

  initial begin
    #1000;
    forever begin
      #2000000;
      $display("[%0t] DIL_PROBE: HB2 fsm0=%0d ctr1=%0d geny=%0d gctr=%0d rdy_geny=%b src_r2=%b src_ready2=%b rstk2=%b dut_rin=%b dut_vin=%b",
               $time, `DAPB.u_dut.cstate0, `DAPB.u_dut.ctr1, `DAPB.u_dut.GEN_Y.cstate, `DAPB.u_dut.GEN_Y.ctr,
               `DAPB.u_dut.ready_i_geny, `DAPB.u_dut.src_read[2], `DAPB.u_dut.src_ready[2], `DAPB.u_dut.rst_k[2],
               `DAPB.dut_rin, `DAPB.dut_vin);
    end
  end

  // ============ 链路探针：LSU→BIU / sysper / icb2apb ============
  `define LSU `CPU_TOP.u_e203_cpu.u_e203_core.u_e203_lsu
  `define BRG u_e203_soc_top.u_icb2apb

  // LSU 发到 BIU 的命令握手
  always @(posedge hfclk) begin
    if (`LSU.biu_icb_cmd_valid & `LSU.biu_icb_cmd_ready)
      $display("[%0t] DIL_PROBE: LSU->BIU %s addr=%h wdata=%h", $time,
               `LSU.biu_icb_cmd_read ? "RD" : "WR", `LSU.biu_icb_cmd_addr, `LSU.biu_icb_cmd_wdata);
  end

  // sysper 口命令/响应握手（e203_soc_top 层）
  always @(posedge hfclk) begin
    if (u_e203_soc_top.sysper_icb_cmd_valid & u_e203_soc_top.sysper_icb_cmd_ready)
      $display("[%0t] DIL_PROBE: SYSPER cmd %s addr=%h wdata=%h", $time,
               u_e203_soc_top.sysper_icb_cmd_read ? "RD" : "WR",
               u_e203_soc_top.sysper_icb_cmd_addr, u_e203_soc_top.sysper_icb_cmd_wdata);
    if (u_e203_soc_top.sysper_icb_rsp_valid & u_e203_soc_top.sysper_icb_rsp_ready)
      $display("[%0t] DIL_PROBE: SYSPER rsp err=%b rdata=%h", $time,
               u_e203_soc_top.sysper_icb_rsp_err, u_e203_soc_top.sysper_icb_rsp_rdata);
  end

  // 桥状态跳变 + cmd_valid 到来
  reg [1:0] last_brg_state;
  initial last_brg_state = 0;
  always @(posedge hfclk) begin
    if (`BRG.state !== last_brg_state) begin
      $display("[%0t] DIL_PROBE: BRG state %0d -> %0d (PADDR=%h)", $time, last_brg_state, `BRG.state, `BRG.PADDR);
      last_brg_state <= `BRG.state;
    end
  end
`endif  // DIL_DEBUG_PROBE


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

   .io_pads_gpioA_i_ival(gpioA_drv),   // [18] = 串口B(UART2) RX，PC→FPGA 注入
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
// PUF 行为模型 + 双串口通道（纯 tb 代码，不改 SoC 任何逻辑）
//
//   串口 B = UART2(0x1003_3000) PC↔FPGA：PC 激励经 gpioA_drv[18] 位bang 注入，
//            uart2_txd 解码实时打 [FPGA]。板上对应 CH340 USB-UART(gpioA[18]/[19])。
//   串口 A = UART1(0x1002_3000) PUF 通道：E203 把 CHAL 原样转发到 uart1_txd，
//            tb 内 PUF 行为模型收 C，计算 R = SHAKE-256(C || DEVICE_CONST)，
//            经 gpioB_drv[16] 位bang 回注 "R <64hex>\r\n"。打 [PUF]。
//   注：PUF 为行为级仿真等效模型（确定性 CRP，单向/不可克隆性为模型假设），
//     非真芯片；DEVICE_CONST = 设备指纹，换值 = 换一颗芯片（DEV plusarg）。
//   物理层：8N1。真机参数 115200；仿真为压缩 wall time
//     用 DLL=1 加速档（bit = 16clk = 64ns），帧格式完全一致。
// =====================================================================
`include "D:/FPGA/e203_hbirdv2-master/tb/shake256_model.v"

localparam UART_BIT_NS = 64;             // 16 clk/bit @ 250MHz(4ns), DLL=1

reg [31:0] gpioA_drv = 32'hFFFF_FFFF;    // UART RX 空闲高电平
reg [31:0] gpioB_drv = 32'hFFFF_FFFF;

`define UART0_TX u_e203_soc_top.u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_perips.uart0_txd
`define UART1_TX u_e203_soc_top.u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_perips.uart1_txd
`define UART2_TX u_e203_soc_top.u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_perips.uart2_txd

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

// ---------------- 串口 B：PC→FPGA 发送（位bang 到 gpioA_drv[18]） ----------------
task pc_send_byte;
  input [7:0] b;
  integer k;
  begin
    gpioA_drv[18] = 1'b0;  #(UART_BIT_NS);               // start
    for (k = 0; k < 8; k = k + 1) begin
      gpioA_drv[18] = b[k];  #(UART_BIT_NS);
    end
    gpioA_drv[18] = 1'b1;  #(UART_BIT_NS + UART_BIT_NS/2); // stop + 间隙
  end
endtask

task pc_send_cmd;                          // 短命令 + CRLF
  input [8*8-1:0] s;
  input integer n;
  integer k;
  begin
    $display("[%0t] [PC] %0s", $time, s);
    for (k = 0; k < n; k = k + 1) pc_send_byte(s[8*(n-k)-1 -: 8]);
    pc_send_byte(8'h0D); pc_send_byte(8'h0A);
  end
endtask

task pc_send_chal;                         // "CHAL " + chal_c 64hex
  integer k;
  reg [7:0] cb;
  begin
    $display("[%0t] [PC] CHAL C=%h (32B)", $time, chal_c);
    pc_send_byte("C"); pc_send_byte("H"); pc_send_byte("A"); pc_send_byte("L"); pc_send_byte(" ");
    for (k = 0; k < 32; k = k + 1) begin
      cb = chal_c[255-8*k -: 8];
      pc_send_byte(to_hex(cb[7:4])); pc_send_byte(to_hex(cb[3:0]));
    end
    pc_send_byte(8'h0D); pc_send_byte(8'h0A);
  end
endtask

task pc_send_fw;                           // "FW " + 2KB(0x00..0xFF 循环) 4096hex；tamper=1 篡改第0字节
  input integer tamper;
  integer k;
  reg [7:0] b;
  begin
    $display("[%0t] [PC] FW 2048B pattern(00..FF cycle) tamper=%0d", $time, tamper);
    pc_send_byte("F"); pc_send_byte("W"); pc_send_byte(" ");
    for (k = 0; k < 2048; k = k + 1) begin
      b = k[7:0];
      if (tamper && (k == 0)) b = b ^ 8'h01;             // 篡改固件 1 字节
      pc_send_byte(to_hex(b[7:4])); pc_send_byte(to_hex(b[3:0]));
    end
    pc_send_byte(8'h0D); pc_send_byte(8'h0A);
  end
endtask

// ---------------- 串口 B：FPGA→PC 接收解码（uart2_txd → [FPGA] + 行解析） ----------------
reg [7:0] fpga_line [0:4991];
integer   fpga_llen = 0;
reg       fpga_bol = 1;
reg       rx0_busy = 0;
reg [7:0] rx0_byte;
integer   b0;
reg [15:0] flags = 0;
localparam F_READY=0, F_KGOK=1, F_FW=2, F_SIG=3, F_OK=4, F_FAIL=5,
           F_PUBK=6, F_PRIV=7, F_WIPED=8, F_DONE=9;
reg [7:0] sig_hex [0:4895];
integer   sig_hex_len = 0;
integer   eval_i;

task fpga_eval_line;
  begin
    if (fpga_llen >= 16 && fpga_line[0]=="E" && fpga_line[1]=="2" && fpga_line[2]=="0" && fpga_line[3]=="3")
      flags[F_READY] = 1;
    if (fpga_llen >= 13 && fpga_line[0]=="R" && fpga_line[1]=="E" && fpga_line[2]=="S" &&
        fpga_line[3]==" " && fpga_line[4]=="K")
      flags[F_KGOK] = 1;
    if (fpga_llen >= 12 && fpga_line[0]=="R" && fpga_line[1]=="E" && fpga_line[2]=="S" &&
        fpga_line[3]==" " && fpga_line[4]=="F")
      flags[F_FW] = 1;
    if (fpga_llen >= 4 && fpga_line[0]=="S" && fpga_line[1]=="I" && fpga_line[2]=="G" && fpga_line[3]==" ") begin
      sig_hex_len = fpga_llen - 4;
      for (eval_i = 0; eval_i < sig_hex_len; eval_i = eval_i + 1)
        sig_hex[eval_i] = fpga_line[4 + eval_i];
      flags[F_SIG] = 1;
      $display("");
      $display("[%0t] [PC] captured SIG (%0d hex chars)", $time, sig_hex_len);
    end
    if (fpga_llen == 2 && fpga_line[0]=="O" && fpga_line[1]=="K") flags[F_OK] = 1;
    if (fpga_llen == 4 && fpga_line[0]=="F" && fpga_line[1]=="A" && fpga_line[2]=="I" && fpga_line[3]=="L") flags[F_FAIL] = 1;
    if (fpga_llen >= 5 && fpga_line[0]=="P" && fpga_line[1]=="U" && fpga_line[2]=="B") flags[F_PUBK] = 1;
    if (fpga_llen >= 5 && fpga_line[0]=="P" && fpga_line[1]=="R" && fpga_line[2]=="I") flags[F_PRIV] = 1;
    if (fpga_llen >= 9 && fpga_line[0]=="R" && fpga_line[1]=="E" && fpga_line[2]=="S" &&
        fpga_line[3]==" " && fpga_line[4]=="W")
      flags[F_WIPED] = 1;
    if (fpga_llen >= 8 && fpga_line[0]=="R" && fpga_line[1]=="E" && fpga_line[2]=="S" &&
        fpga_line[3]==" " && fpga_line[4]=="D")
      flags[F_DONE] = 1;
    resp_cnt = resp_cnt + 1;
  end
endtask

task fpga_handle_byte;
  input [7:0] ch;
  integer pi;
  begin
    if (ch == 8'h0A) begin
      fpga_eval_line;
      // 整行带角色前缀打印（实时逐字符流由冻结 RTL uart_tx.v 的 $fwrite 提供，
      // 若再打逐字符会与之重复——见 UART_PROTOCOL.md 说明）
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

always @(negedge `UART2_TX) begin
  if (!rx0_busy && rst_n) begin
    rx0_busy = 1;
    #(UART_BIT_NS/2);                    // 起始位中点：先确认不是毛刺
    if (`UART2_TX === 1'b0) begin
      #(UART_BIT_NS);                    // → bit0 中点
      for (b0 = 0; b0 < 8; b0 = b0 + 1) begin
        rx0_byte[b0] = `UART2_TX;
        #(UART_BIT_NS);
      end
      if (`UART2_TX === 1'b1)            // 停止位校验，防假触发
        fpga_handle_byte(rx0_byte);
    end
    rx0_busy = 0;
  end
end

// ---------------- 串口 B 线上行解码：PC→FPGA 实际波形（gpioA_drv[18]） ----------------
reg [7:0] pc_line [0:4991];
integer   pc_llen = 0;
reg       pcrx_busy = 0;
reg [7:0] pcrx_byte;
integer   pb0;

always @(negedge gpioA_drv[18]) begin
  if (!pcrx_busy && rst_n) begin : pcrx_blk
    integer pi;
    pcrx_busy = 1;
    #(UART_BIT_NS/2);
    if (gpioA_drv[18] === 1'b0) begin
      #(UART_BIT_NS);
      for (pb0 = 0; pb0 < 8; pb0 = pb0 + 1) begin
        pcrx_byte[pb0] = gpioA_drv[18];
        #(UART_BIT_NS);
      end
      if (gpioA_drv[18] === 1'b1) begin
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
integer   dev_sel = 0;
reg [255:0] dev_const = {32{8'hA5}};      // DEVICE_CONST：设备指纹（DEV=1 换 0x5A×32）
reg [255:0] chal_c;                       // 挑战 C（+CHAL=<64hex> 覆盖，默认 00..1f）

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
      $display("[%0t] [PUF] DEVICE_CONST=%h (模型等效设备指纹, DEV=%0d)", $time, dev_const, dev_sel);
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

// ---------------- PC 激励（固件库角色，SCEN=A/B/C/D，DEV=0/1） ----------------
// 响应唤醒：fpga_eval_line 每收到一行 resp_cnt++；wait_resp 等待下一行或超时
integer resp_cnt = 0;

task wait_flag;                       // 轮询 flags[bitno]，超时 $finish
  input integer bitno;
  input [8*40-1:0] msg;
  input integer ns;
  integer waited;
  begin
    waited = 0;
    while ((!flags[bitno]) && (waited < ns)) begin
      #1000;
      waited = waited + 1000;
    end
    if (!flags[bitno]) begin
      $display("[%0t] [PC] TIMEOUT waiting %0s", $time, msg);
      $finish;
    end
  end
endtask

task wait_line;                       // 等到 resp_cnt 再 +1（重复命令的响应）
  input [8*40-1:0] msg;
  input integer ns;
  integer before;
  integer waited;
  begin
    before = resp_cnt;
    waited = 0;
    while ((resp_cnt == before) && (waited < ns)) begin
      #1000;
      waited = waited + 1000;
    end
    if (resp_cnt == before) begin
      $display("[%0t] [PC] TIMEOUT waiting %0s", $time, msg);
      $finish;
    end
  end
endtask

initial begin : pc_actor
  reg [8*8-1:0] scen;
  integer tamper_pos;
  begin
    if (!$value$plusargs("SCEN=%s", scen)) scen = "A";
    if (!$value$plusargs("DEV=%d", dev_sel)) dev_sel = 0;
    dev_const = (dev_sel == 1) ? {32{8'h5A}} : {32{8'hA5}};
    if (!$value$plusargs("TAMPER_POS=%d", tamper_pos)) tamper_pos = 100;
    for (b0 = 0; b0 < 32; b0 = b0 + 1) chal_c[255-8*b0 -: 8] = b0[7:0];   // 默认 C = 00..1f
    if ($value$plusargs("CHAL=%h", chal_c))
      $display("[%0t] [PC] custom CHAL=%h", $time, chal_c);

    wait_flag(F_READY, "firmware ready", 50000000);
    $display("[%0t] [PC] ==== SCENARIO %0s start (DEV=%0d, C=%h, DEVICE_CONST=%h) ====", $time, scen, dev_sel, chal_c, dev_const);

    // ① 固件库发送挑战 C（串口B）→ E203 转发（串口A）→ PUF → R → keygen
    // 前导同步帧：2×HELP。首帧吸收幻影字节（GPIO 同步链复位释放晚 + 接收状态机
    // 首帧相位异常，实测 2~8 字节，详见 UART_PROTOCOL.md 遗留问题节）；
    // 第二发 HELP 应返回干净帮助文本 = 锁定确认。
    pc_send_cmd("HELP", 4); wait_line("HELP #1 (sync frame)", 20000000);
    pc_send_cmd("HELP", 4); wait_line("HELP #2 (lock confirm)", 20000000);
    #50000;
    pc_send_chal;
    wait_flag(F_KGOK, "RES KEYGEN OK", 50000000);

    if (scen == "A") begin
      pc_send_cmd("PUBK", 4); wait_flag(F_PUBK, "PUBK", 10000000);
      pc_send_cmd("PRIV", 4); wait_flag(F_PRIV, "PRIV", 20000000);
      pc_send_fw(0);      wait_flag(F_FW, "RES FW SHA3", 20000000);
      pc_send_cmd("SIGN", 4); wait_flag(F_SIG, "SIG", 50000000);
      pc_send_byte("V"); pc_send_byte("E"); pc_send_byte("R"); pc_send_byte(" ");
      $display("[%0t] [PC] VER <SIG %0d hex, 无篡改>", $time, sig_hex_len);
      for (b0 = 0; b0 < sig_hex_len; b0 = b0 + 1) pc_send_byte(sig_hex[b0]);
      pc_send_byte(8'h0D); pc_send_byte(8'h0A);
      wait_line("OK/FAIL", 50000000); if (!flags[F_OK] && !flags[F_FAIL]) begin $display("[%0t] [PC] TIMEOUT waiting verdict", $time); $finish; end
      if (flags[F_OK]) $display("[%0t] [PC] SCEN_RESULT: A PASS (verify OK as expected)", $time);
      else        $display("[%0t] [PC] SCEN_RESULT: A ***MISMATCH*** (expected OK, got FAIL)", $time);
      pc_send_cmd("WIPE", 4); wait_flag(F_WIPED, "RES WIPED", 10000000);
      pc_send_cmd("DONE", 4);
    end
    else if (scen == "B") begin                 // 篡改签名 1 字节 → 必须 FAIL
      pc_send_fw(0);      wait_flag(F_FW, "RES FW SHA3", 20000000);
      pc_send_cmd("SIGN", 4); wait_flag(F_SIG, "SIG", 50000000);
      $display("[%0t] [PC] VER <SIG %0d hex, 篡改 hex[%0d..%0d]=1 字节>", $time, sig_hex_len, tamper_pos, tamper_pos+1);
      pc_send_byte("V"); pc_send_byte("E"); pc_send_byte("R"); pc_send_byte(" ");
      for (b0 = 0; b0 < sig_hex_len; b0 = b0 + 1) begin
        if (b0 == tamper_pos || b0 == tamper_pos + 1)
          pc_send_byte(sig_hex[b0] == "0" ? "1" : "0");
        else
          pc_send_byte(sig_hex[b0]);
      end
      pc_send_byte(8'h0D); pc_send_byte(8'h0A);
      wait_line("OK/FAIL", 50000000); if (!flags[F_OK] && !flags[F_FAIL]) begin $display("[%0t] [PC] TIMEOUT waiting verdict", $time); $finish; end
      if (flags[F_FAIL]) $display("[%0t] [PC] SCEN_RESULT: B PASS (tampered sig -> FAIL as expected)", $time);
      else          $display("[%0t] [PC] SCEN_RESULT: B ***MISMATCH*** (expected FAIL, got OK)", $time);
      pc_send_cmd("DONE", 4);
    end
    else if (scen == "C") begin                 // 篡改固件 1 字节（换摘要） → 必须 FAIL
      pc_send_fw(0);      wait_flag(F_FW, "RES FW SHA3 #1", 20000000);
      pc_send_cmd("SIGN", 4); wait_flag(F_SIG, "SIG", 50000000);
      pc_send_fw(1);      wait_line("RES FW SHA3 #2 (tampered)", 20000000);
      $display("[%0t] [PC] VER <SIG %0d hex 原签名 vs 篡改后固件摘要>", $time, sig_hex_len);
      pc_send_byte("V"); pc_send_byte("E"); pc_send_byte("R"); pc_send_byte(" ");
      for (b0 = 0; b0 < sig_hex_len; b0 = b0 + 1) pc_send_byte(sig_hex[b0]);
      pc_send_byte(8'h0D); pc_send_byte(8'h0A);
      wait_line("OK/FAIL", 50000000); if (!flags[F_OK] && !flags[F_FAIL]) begin $display("[%0t] [PC] TIMEOUT waiting verdict", $time); $finish; end
      if (flags[F_FAIL]) $display("[%0t] [PC] SCEN_RESULT: C PASS (tampered fw -> FAIL as expected)", $time);
      else          $display("[%0t] [PC] SCEN_RESULT: C ***MISMATCH*** (expected FAIL, got OK)", $time);
      pc_send_cmd("DONE", 4);
    end
    else if (scen == "D") begin                 // PUF 唯一性：换 DEVICE_CONST 比对 PUBK
      pc_send_cmd("PUBK", 4); wait_flag(F_PUBK, "PUBK", 10000000);
      $display("[%0t] [PC] SCEN_RESULT: D done (DEV=%0d; compare PUBK across DEV runs)", $time, dev_sel);
      pc_send_cmd("DONE", 4);
    end
    else begin
      $display("[%0t] [PC] unknown SCEN=%0s", $time, scen);
      $finish;
    end
  end
end


// ============ uart_rx_i 内部诊断探针（首帧幻影字节定位用） ============
`ifdef UART_RX_DEBUG
`define U0RX u_e203_soc_top.u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_perips.u_perips_apb_uart0.uart_rx_i
`define U1RX u_e203_soc_top.u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_perips.u_perips_apb_uart1.uart_rx_i
reg [2:0] last_u0cs = 0;
initial begin
  forever begin
    @(`U0RX.CS, `U0RX.rx_valid_o);
    if (1) begin end
  end
  forever begin
    @(`U1RX.CS, `U1RX.rx_valid_o);
    if ($time < 120000000 && rst_n)
      $display("[%0t] U0RX CS=%0d fall=%b sync=%b bitdone=%b sample=%b valid=%b data=%h baud=%0d div=%0d",
        $time, `U0RX.CS, `U0RX.s_rx_fall, `U0RX.reg_rx_sync, `U0RX.bit_done,
        `U0RX.sampleData, `U0RX.rx_valid_o, `U0RX.reg_data, `U0RX.baud_cnt, `U0RX.cfg_div_i);
  end
  forever begin
    @( `U1RX.CS );
  end
end
initial begin
  forever begin
    @(`U1RX.CS, `U1RX.rx_valid_o);
    if ($time < 400000000 && rst_n)
      $display("[%0t] U1RX CS=%0d fall=%b sync=%b bitdone=%b valid=%b data=%h baud=%0d div=%0d",
        $time, `U1RX.CS, `U1RX.s_rx_fall, `U1RX.reg_rx_sync, `U1RX.bit_done,
        `U1RX.rx_valid_o, `U1RX.reg_data, `U1RX.baud_cnt, `U1RX.cfg_div_i);
  end
end
`endif

endmodule


