# 板级构建值班记录（2026-10-14 夜）

## 最终结果（第五轮构建，23:49 完成）
- `system.bit` 已生成：`my_fpga/mcu200t_board/mcu200t_board.runs/impl_1/system.bit`（9.7MB）
- 资源：Slice LUTs 66,452/133,800（49.67%）、寄存器 40,125（14.99%）、BRAM 67/365（18.4%）
- 时序：WNS=0.000，TNS=0，0 个违例端点；保持时间 WHS=0.051 同样干净（16MHz 主时钟 clk_out2_mmcm，62.5ns 周期）
- 功能验证：场景 A 回归 PASS + TEST_PASS，总周期数 6,606,190 与改动前**逐拍一致**，金样全对（reg_ram_scenA.log）

## 今夜五轮构建的问题与修复
1. **多驱动 DRC**（done/rptr 被两个 always 块驱动）→ 合并驱动源到单一块（dilithium_apb.v）
2. **LUT 超标 135%**（inbuf/outbuf 24KB 被综合成 19.7 万触发器+巨阵选择器）→ 拆偶/奇双 bank
3. **布局器拒绝**（寄存器 89% 占用，bank 化后仍是 FF：写在带复位的 always 块里无法推断 BRAM）
4. **根因修复**：放弃推断，改为显式实例化仓库自带的 `dual_port_ram`（combined_top 内部同款、已被证明映射 RAMB36）。
   inbuf/outbuf 各拆 hi/lo 两个实例（共 4 个，+6 块 RAMB36）。读延迟与原 FF 方案逐拍一致：
   - inbuf 读地址组合给出（S_IN 且 rin 时取 ctr+1），RAM 内 dob 寄存器替代原 dut_din FF
   - outbuf 读地址在 APB 建立相位给出（rptr>>1），访问相位 dob 有效，PRDATA 时序不变
5. tb_top.v 探针同步改到新层级（`u_inbuf_hi.ram[..]` 等）
6. 注意：xsim 库出现 `--incr` 增量编译卡死现象（与代码无关），手动流程：删 tb_top.sdb → xvlog（不带 --incr）→ xelab → xsim，见 reg_ram_scenA.log 对应命令

## 板型确认
- 用户确认为 **DDR200T**：约束用 `fpga/ddr200t/constrs/`（build.tcl 已指向），`ddr200t/src/system.v` 已同步 bootrom_n=0（上电 MROM→ITCM，JTAG 下固件）
- DDR200T 的 USB 串口在 **UART0**（gpioA[16]/[17]）；gpioA[18]/[19] 是 Lora 接口
- 板级固件两版已备好：`Dilithium-master/test_board_uart0.elf`（首选）、`test_board.elf`（UART2/Lora 引脚备用）

## 烧板待办（用户侧）
1. Hardware Manager 烧 system.bit（FPGA JTAG）
2. NucleiStudio/openocd 经蜂鸟调试器下 test_board_uart0.elf 到 ITCM
3. CH340/板载串口 115200 8N1，上位机切串口后端跑 SEED→KEYGEN→PUBK/PRIV→FW→SIGN→VER
4. 可选：GUI Generate Memory Configuration File（MCS/SPIx4/16MB/0x0）烧 FLASH 做持久化
