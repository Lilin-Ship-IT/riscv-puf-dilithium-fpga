module _verify_top(input clk, input [7:0] d, output reg [7:0] q);
always @(posedge clk) q <= d + 8'd1;
endmodule
