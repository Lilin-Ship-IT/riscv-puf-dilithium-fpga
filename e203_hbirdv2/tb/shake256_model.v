/*
 * shake256_model.v — 纯行为级 SHAKE-256 模型（仅用于 testbench，综合无关）
 *
 * 用途: E203+Dilithium+PUF 演示的 tb 侧 PUF 行为模型
 *       R = SHAKE-256(C || DEVICE_CONST)
 * 算法来源: FIPS 202；与固件 sha3_sw.c 共用同一 tiny_sha3 轮常数表
 *          (Markku-Juhani O. Saarinen, CC0/Public Domain)
 * 验证: 与 Python hashlib.shake_256 逐字节比对通过（sim_logs/shake256_model_tb.log）
 *
 * 用法: 在 tb 模块内 `include 本文件，调用 shake256(msg, nbytes, digest)
 *   msg    — 定长 160B 域左对齐打包，bit [8*160-1 -: 8] 为第 0 字节，nbytes 之后忽略
 *   nbytes — 消息字节数, 1..160
 *   digest — 256bit 输出，bit [255 -: 8] 为输出第 0 字节
 * 注意: 所有内部状态用模块级 sk_/puf_ 前缀寄存器（Verilog-2001 不能传数组给 task）
 */

reg [63:0] sk_rndc [0:23];
reg [5:0]  sk_rotc [0:23];
reg [4:0]  sk_piln [0:23];
reg [63:0] sk_st [0:24];
reg [7:0]  sk_sb [0:199];
reg        sk_tables_done = 0;

task sk_init_tables;
begin
    sk_rndc[ 0]=64'h0000000000000001; sk_rndc[ 1]=64'h0000000000008082;
    sk_rndc[ 2]=64'h800000000000808a; sk_rndc[ 3]=64'h8000000080008000;
    sk_rndc[ 4]=64'h000000000000808b; sk_rndc[ 5]=64'h0000000080000001;
    sk_rndc[ 6]=64'h8000000080008081; sk_rndc[ 7]=64'h8000000000008009;
    sk_rndc[ 8]=64'h000000000000008a; sk_rndc[ 9]=64'h0000000000000088;
    sk_rndc[10]=64'h0000000080008009; sk_rndc[11]=64'h000000008000000a;
    sk_rndc[12]=64'h000000008000808b; sk_rndc[13]=64'h800000000000008b;
    sk_rndc[14]=64'h8000000000008089; sk_rndc[15]=64'h8000000000008003;
    sk_rndc[16]=64'h8000000000008002; sk_rndc[17]=64'h8000000000000080;
    sk_rndc[18]=64'h000000000000800a; sk_rndc[19]=64'h800000008000000a;
    sk_rndc[20]=64'h8000000080008081; sk_rndc[21]=64'h8000000000008080;
    sk_rndc[22]=64'h0000000080000001; sk_rndc[23]=64'h8000000080008008;

    sk_rotc[ 0]=1;  sk_rotc[ 1]=3;  sk_rotc[ 2]=6;  sk_rotc[ 3]=10;
    sk_rotc[ 4]=15; sk_rotc[ 5]=21; sk_rotc[ 6]=28; sk_rotc[ 7]=36;
    sk_rotc[ 8]=45; sk_rotc[ 9]=55; sk_rotc[10]=2;  sk_rotc[11]=14;
    sk_rotc[12]=27; sk_rotc[13]=41; sk_rotc[14]=56; sk_rotc[15]=8;
    sk_rotc[16]=25; sk_rotc[17]=43; sk_rotc[18]=62; sk_rotc[19]=18;
    sk_rotc[20]=39; sk_rotc[21]=61; sk_rotc[22]=20; sk_rotc[23]=44;

    sk_piln[ 0]=10; sk_piln[ 1]=7;  sk_piln[ 2]=11; sk_piln[ 3]=17;
    sk_piln[ 4]=18; sk_piln[ 5]=3;  sk_piln[ 6]=5;  sk_piln[ 7]=16;
    sk_piln[ 8]=8;  sk_piln[ 9]=21; sk_piln[10]=24; sk_piln[11]=4;
    sk_piln[12]=15; sk_piln[13]=23; sk_piln[14]=19; sk_piln[15]=13;
    sk_piln[16]=12; sk_piln[17]=2;  sk_piln[18]=20; sk_piln[19]=14;
    sk_piln[20]=22; sk_piln[21]=9;  sk_piln[22]=6;  sk_piln[23]=1;
end
endtask

// keccak-f[1600] 置换（操作模块级 sk_st）
task sk_keccakf;
    integer r, i, j;
    reg [63:0] t;
    reg [63:0] bc [0:4];
begin
    for (r = 0; r < 24; r = r + 1) begin
        // Theta
        for (i = 0; i < 5; i = i + 1)
            bc[i] = sk_st[i] ^ sk_st[i+5] ^ sk_st[i+10] ^ sk_st[i+15] ^ sk_st[i+20];
        for (i = 0; i < 5; i = i + 1) begin
            t = bc[(i+4)%5] ^ {bc[(i+1)%5][62:0], bc[(i+1)%5][63]};
            for (j = 0; j < 25; j = j + 5)
                sk_st[j+i] = sk_st[j+i] ^ t;
        end
        // Rho + Pi
        t = sk_st[1];
        for (i = 0; i < 24; i = i + 1) begin
            j = sk_piln[i];
            bc[0] = sk_st[j];
            sk_st[j] = (t << sk_rotc[i]) | (t >> (64 - sk_rotc[i]));
            t = bc[0];
        end
        // Chi
        for (j = 0; j < 25; j = j + 5) begin
            for (i = 0; i < 5; i = i + 1)
                bc[i] = sk_st[j+i];
            for (i = 0; i < 5; i = i + 1)
                sk_st[j+i] = sk_st[j+i] ^ ((~bc[(i+1)%5]) & bc[(i+2)%5]);
        end
        // Iota
        sk_st[0] = sk_st[0] ^ sk_rndc[r];
    end
end
endtask

// 状态字节视图 <-> lane 视图（小端）
task sk_bytes_to_lanes;
    integer lane, sh;
begin
    for (lane = 0; lane < 25; lane = lane + 1) begin
        sk_st[lane] = 64'd0;
        for (sh = 0; sh < 8; sh = sh + 1)
            sk_st[lane][8*sh +: 8] = sk_sb[lane*8+sh];
    end
end
endtask

task sk_lanes_to_bytes;
    integer lane, sh;
begin
    for (lane = 0; lane < 25; lane = lane + 1)
        for (sh = 0; sh < 8; sh = sh + 1)
            sk_sb[lane*8+sh] = sk_st[lane][8*sh +: 8];
end
endtask

// SHAKE-256: rate=136B, 域分隔 0x1F，输出 32B
task shake256;
    input  [8*160-1:0] msg;
    input  integer     nbytes;
    output [255:0]     digest;
    integer i, pos;
    reg [7:0] b;
begin
    if (!sk_tables_done) begin
        sk_init_tables;
        sk_tables_done = 1;
    end
    for (i = 0; i < 200; i = i + 1) sk_sb[i] = 8'd0;
    pos = 0;
    // 吸收
    for (i = 0; i < nbytes; i = i + 1) begin
        b = msg[8*160-1 - 8*i -: 8];   // 定长 160B 域左对齐，第 i 字节
        sk_sb[pos] = sk_sb[pos] ^ b;
        pos = pos + 1;
        if (pos == 136) begin
            sk_bytes_to_lanes;
            sk_keccakf;
            sk_lanes_to_bytes;
            pos = 0;
        end
    end
    // 填充: SHAKE 域 0x1F + 末位 0x80
    sk_sb[pos] = sk_sb[pos] ^ 8'h1F;
    sk_sb[135] = sk_sb[135] ^ 8'h80;
    sk_bytes_to_lanes;
    sk_keccakf;
    // 挤压前 32 字节（一个 rate 块足够）
    for (i = 0; i < 32; i = i + 1)
        digest[255 - 8*i -: 8] = sk_st[i/8][8*(i%8) +: 8];
end
endtask
