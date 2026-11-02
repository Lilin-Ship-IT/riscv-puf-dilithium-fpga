// ICB(slave) -> APB(master) 桥：把 E203 sysper 总线转成 dilithium_apb 的 APB 口
module icb2apb (
  input  wire        clk,
  input  wire        rst_n,

  // ICB slave（接 E203 sysper 主口）
  input  wire        i_icb_cmd_valid,
  output wire        i_icb_cmd_ready,
  input  wire [31:0] i_icb_cmd_addr,
  input  wire        i_icb_cmd_read,
  input  wire [31:0] i_icb_cmd_wdata,
  input  wire [3:0]  i_icb_cmd_wmask,
  output reg         i_icb_rsp_valid,
  input  wire        i_icb_rsp_ready,
  output wire        i_icb_rsp_err,
  output reg  [31:0] i_icb_rsp_rdata,

  // APB master（接 dilithium_apb）
  output reg         PSEL,
  output reg         PENABLE,
  output reg         PWRITE,
  output reg  [31:0] PADDR,
  output reg  [31:0] PWDATA,
  input  wire [31:0] PRDATA,
  input  wire        PREADY
);

  localparam S_IDLE=2'd0, S_SETUP=2'd1, S_ACCESS=2'd2, S_RSP=2'd3;
  reg [1:0] state;

  assign i_icb_cmd_ready = (state == S_IDLE);   // 单发缓冲，够外设用
  assign i_icb_rsp_err   = 1'b0;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state <= S_IDLE;
      PSEL <= 1'b0; PENABLE <= 1'b0; PWRITE <= 1'b0;
      PADDR <= 32'b0; PWDATA <= 32'b0;
      i_icb_rsp_valid <= 1'b0; i_icb_rsp_rdata <= 32'b0;
    end else case (state)
      S_IDLE: if (i_icb_cmd_valid) begin
        PSEL    <= 1'b1; PENABLE <= 1'b0;
        PWRITE  <= ~i_icb_cmd_read;
        PADDR   <= i_icb_cmd_addr;
        PWDATA  <= i_icb_cmd_wdata;      // wmask 忽略：驱动保证对齐 32 位全字访问
        state   <= S_SETUP;
      end
      S_SETUP: begin PENABLE <= 1'b1; state <= S_ACCESS; end
      S_ACCESS: if (PREADY) begin
        PSEL <= 1'b0; PENABLE <= 1'b0;
        i_icb_rsp_rdata <= PRDATA;
        i_icb_rsp_valid <= 1'b1;
        state <= S_RSP;
      end
      default: if (i_icb_rsp_ready) begin   // S_RSP
        i_icb_rsp_valid <= 1'b0;
        state <= S_IDLE;
      end
    endcase
  end
endmodule