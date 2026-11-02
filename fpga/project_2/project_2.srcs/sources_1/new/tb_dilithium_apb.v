`timescale 1ns/1ps
module tb_dilithium_apb;
  reg clk=0, rst_n=0;
  reg [31:0] paddr=0, pwdata=0; reg psel=0, penable=0, pwrite=0;
  wire [31:0] prdata; wire pready, irq;

  dilithium_apb DUT(.PCLK(clk), .PRESETn(rst_n), .PADDR(paddr), .PSEL(psel),
    .PENABLE(penable), .PWRITE(pwrite), .PWDATA(pwdata), .PRDATA(prdata),
    .PREADY(pready), .irq_o(irq));

  always #5 clk = ~clk;

  task apb_wr(input [31:0] a, input [31:0] d);
    begin
      @(negedge clk); paddr=a; pwdata=d; pwrite=1; psel=1; penable=0;
      @(negedge clk); penable=1;
      @(negedge clk); psel=0; penable=0;
    end
  endtask

  task apb_rd(input [31:0] a, output [31:0] d);
    begin
      @(negedge clk); paddr=a; pwrite=0; psel=1; penable=0;
      @(negedge clk); penable=1;
      @(negedge clk); d=prdata; psel=0; penable=0;
    end
  endtask

  // 不含 m 段的固定 64-bit 字数（rho4+c4+z+t1+mlen1+h）
  function integer sec64(input integer lvl);
    case(lvl) 2: sec64=4+4+288+160+1+11; 3: sec64=4+4+400+240+1+8;
              default: sec64=4+4+560+320+1+11; endcase
  endfunction

  integer lvl, tv, i, nwords, fails; reg [31:0] st, mlens[0:4];
  reg [31:0] stream[0:13999];                  // 5 TV x 2700 字

  initial begin
    rst_n=0; fails=0;
    repeat(5) @(negedge clk); rst_n=1;
    for (lvl=2; lvl<=5; lvl=(lvl==2)?3:(lvl==3)?5:6) begin   // 2->3->5->退出
case (lvl)
  2: begin
       $readmemh("D:/FPGA/Dilithium-master/KAT/hex/kat_stream_lv2.hex", stream);
       $readmemh("D:/FPGA/Dilithium-master/KAT/hex/kat_mlen_lv2.hex",  mlens);
     end
  3: begin
       $readmemh("D:/FPGA/Dilithium-master/KAT/hex/kat_stream_lv3.hex", stream);
       $readmemh("D:/FPGA/Dilithium-master/KAT/hex/kat_mlen_lv3.hex",  mlens);
     end
  default: begin
       $readmemh("D:/FPGA/Dilithium-master/KAT/hex/kat_stream_lv5.hex", stream);
       $readmemh("D:/FPGA/Dilithium-master/KAT/hex/kat_mlen_lv5.hex",  mlens);
     end
endcase
      for (tv=0; tv<5; tv=tv+1) begin
        nwords = 2*(sec64(lvl) + (mlens[tv]+7)/8);       // 该 TV 总 32-bit 字数
        apb_wr(32'h10, 0);                                   // PTR=0
        for (i=0; i<nwords; i=i+1)
          apb_wr(32'h14, stream[tv*2700 + i]);               // 写输入缓冲
        apb_wr(32'h08, mlens[tv]);                           // MLEN
        apb_wr(32'h00, (lvl<<4) | (1<<1) | 1);               // CTRL: start, mode=1(verify)
        begin : poll
          reg [31:0] s; s = 0;
          while (!s[1]) apb_rd(32'h04, s);                   // 轮询 done
        end
        apb_rd(32'h04, st);
        if (st[2]) begin fails=fails+1; $display("FAIL  lvl%0d tv%0d", lvl, tv); end
        else $display("PASS  lvl%0d tv%0d", lvl, tv);
      end
    end
    if (fails==0) $display("ALL TESTS PASSED");
    else $display("%0d TESTS FAILED", fails);
    $finish;
  end
endmodule