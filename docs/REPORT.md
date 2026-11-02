# E203 + Dilithium 后量子签名加速器 SoC 联合仿真验证报告

日期：2026-10-03
结论：**官方 15 组 KAT（5 tv × lv2/lv3/lv5）全部 PASS，三轮 tb 均打印 TEST_PASS。**

## 1. 环境

- Vivado 2019.2，工程 `D:\FPGA\my_fpga\e203_sim\e203_sim.xpr`（顶层 tb_top，行为仿真 sim_1）
- RTL：`D:\FPGA\e203_hbirdv2-master\`（备份：`D:\FPGA\e203_hbirdv2-master-bak\`）
- 软件：`D:\FPGA\Dilithium-master\`（main_lv2/3/5.c、dilithium_drv.h、start.S、link.ld、kat_lv2/3/5.h）
- 工具链：`D:\FPGA\NucleiStudio\NucleiStudio\toolchain\gcc\bin\riscv-nuclei-elf-gcc.exe`（gcc 10.2.0）
- 运行方式：`vivado -mode batch -source run_sim.tcl`（`D:\FPGA\sim_logs\run_sim.tcl`），不开 GUI

## 2. 编译命令（未改动）

```
riscv-nuclei-elf-gcc.exe -Os -march=rv32imac -mabi=ilp32 -nostdlib -ffreestanding -T link.ld start.S main.c -o test.elf
riscv-nuclei-elf-objcopy.exe -O verilog --change-addresses=-2147483648 test.elf test.verilog
copy test.verilog D:\FPGA\my_fpga\e203_sim\e203_sim.sim\sim_1\behav\xsim\
```

## 3. 数据通路（文字版）

```
C 程序 (dilithium_drv.h, 基址 0x1100_0000)
  → E203 CPU LSU → BIU（PPI 区 0x1000_0000-0x1FFF_FFFF）
  → ppi → perips 译码器 O12 窗口（0x1100_0000-0x11FF_FFFF，16MB）
  → sysper ICB 口（e203_soc_top 层引出）
  → icb2apb 桥（ICB slave → APB master，单发缓冲 4 态 FSM）
  → dilithium_apb（APB 寄存器组 + inbuf 4096×32b + outbuf + 流式 FSM）
  → combined_top（Dilithium 组合逻辑 datapath）
```

寄存器映射（dilithium_apb）：0x00 CTRL（[0]start [2:1]mode [6:4]sec_lvl）、
0x04 STATUS（[0]busy [1]done [2]result/reject）、0x08 MLEN、0x10 PTR、
0x14 WDATA（写后 ptr 自增）、0x1C RDATA。
输入流顺序：rho(8) | c(8) | z | t1 | {0,mlen} | m | h（32-bit 字，与 KAT hex 同序）。

## 4. 结果：15/15 PASS

| 轮次 | 级别 | 组数 | CTRL | 每组结果 | tb 结论 | log |
|------|------|------|------|----------|---------|-----|
| 1 | lv2 | 5 | 0x23 | 5×done=1 result=0 | TEST_PASS | sim_full_lv2_console.log |
| 2 | lv3 | 5 | 0x33 | 5×done=1 result=0 | TEST_PASS | sim_full_lv3_console.log |
| 3 | lv5 | 5 | 0x53 | 5×done=1 result=0 | TEST_PASS | sim_full_lv5_console.log |

- 每组证据链完整：wptr 灌满（946~978 / 1324~1356 / 1810~1842 字）→ CTRL 写 start
  → busy 1→0 → done=1 result=0（验签通过）→ 最后 x3(gp)=1 → TEST_PASS
- lv5 全轮 cycle_count=178651，final x3=1
- 关键事件时间戳见 `KEY_EVENTS_lv2/3/5.md`；波形库 `wave_full_lv5.wdb`
  （wptr/busy/done/state/sysper/x3 已 log_wave，可用 Vivado 打开截屏）

**为什么拆 3 轮**：15 组 KAT rodata 约 130KB，超过 ITCM 硬件 64KB（链接器报
`region ITCM overflowed by 65652 bytes`）。link.ld 与编译参数按红线冻结，
故按级别拆成 3 个固件各跑 5 组（各自 35KB/43KB/53KB，均 <64KB）。

## 5. 遇到的问题与解决（共 4 个，按发现顺序）

### 坑 1（历史已知）：基地址 0x1000_0000 撞 PPI 段基址
0x1000_0000 访问被 perips 译码器路由进 AON 域，几十笔写后总线挂死。
已在前期改为 0x1100_0000（O12 sysper 外窗口）。本报告不再赘述。

### 坑 2（根因级）：e203_soc_top.v 的加速器时钟是幻影网络
- 现象：CPU 发出第一笔写 `0x1100_00010`（LSU→BIU ✔、sysper cmd 握手 ✔）后无任何
  响应，pc 永久停在 dil_load 的 load（0x80000026），40ms 超时。
- 定位：桥/加速器的 `.clk/.PCLK` 接的是 `hfclk`，但该标识符在 e203_soc_top 层
  **从未声明、从未驱动** → Verilog 隐式生成无驱动 1-bit 网线（恒 Z）→ 两模块时钟
  从未翻转，复位沿后所有寄存器冻在 0。桥的 cmd_ready 是组合逻辑恒 1，命令被"收下"
  却无人处理 → rsp 永不返回 → CPU 挂死。
- 修复（仅 2 行时钟引脚，数据通路未动，见 `rtl/e203_soc_top_fix.diff`）：
  `.clk/.PCLK` 改接 `u_e203_subsys_top.hfclk`（子系统内部真实主时钟，层次引用）。
- 教训：单测过的模块集成后仍要查时钟/复位；xsim 对隐式网线只给 warning。

### 坑 3：驱动每段清写指针，输入流被逐段覆盖
- 现象：时钟修复后加速器启动，但流式 FSM 停在 S_IN ctr=469（DUT 停止收数）；
  心跳里 wptr 终值=22（恰好等于最后一段 h 的字数）——铁证：dil_load 每段都
  `DIL_PTR=0`，rho/c/z/t1/m 全被后段覆盖，inbuf 只剩 h。FSM 按 MLEN 寄存器算
  输入字数，DUT 按流里垃圾 mlen 解析，两者消耗不一致 → 卡死。
- 修复（dilithium_drv.h）：`DIL_PTR=0` 移到 dilithium_verify 开头，整段流只清一次。

### 坑 4a：APB 读时序 —— 复位后首笔读必为 X
- dilithium_apb 的 PRDATA 是寄存器输出，桥在 access 拍末采样到的是**上一笔读**的
  旧值；复位后首笔 STATUS 读返回 X，CPU `beqz` 判 X 后 X 传播锁死
  （log 里 `SYSPER rsp rdata=xxxxxxxx`）。RTL 冻结不能改。
- 规避（dilithium_drv.h）：CTRL 启动后先哑读一次 STATUS 冲掉 X；之后轮询读到的
  只是落后一拍的真实状态，不影响 done/reject 判断。

### 坑 4b：gp(x3) 写被 gcc -Os 当死代码删除
- 验签实际已通过（done=1 result=0），但 tb 等不到 x3==1，40ms 超时。
  反汇编确认 `register uint32_t gp asm("x3"); gp=...` 未生成任何指令。
- 修复（main.c）：`asm volatile ("mv x3, %0" :: "r"(r))`，确认生成 `mv gp,a5`。

## 6. 产物清单（D:\FPGA\sim_logs\）

| 文件 | 说明 |
|------|------|
| sim_run1~5_console.log | 分诊过程的 5 轮 log（含两次失败根因现场） |
| sim_full_lv2/3/5_console.log | **三轮全量 log，均 TEST_PASS** |
| KEY_EVENTS_lv2/3/5.md | 每组 CTRL/done/result/x3 关键时间戳 |
| wave_full_lv5.wdb | lv5 全轮波形库（加速器/sysper/x3 关键信号） |
| fw/ | 三份 test.elf + test.verilog + main_lv*.c + dilithium_drv.h + start.S + link.ld 定稿 |
| rtl/ | tb_top.v（探针版）、e203_soc_top.v（修复版）、两份 diff |
| run_sim.tcl / run_sim_wave.tcl | 复现脚本 |
| PROGRESS.md | 过程日志 |

## 7. 复现步骤

1. `cd D:\FPGA\Dilithium-master`，`copy main_lvX.c main.c`，按第 2 节命令编译并拷 test.verilog
2. `vivado -mode batch -source D:\FPGA\sim_logs\run_sim.tcl`
3. console log 末尾应见 5×`done -> 1 result=0` 与 `TEST_PASS`

## 8. 备注

- 红线遵守：rtl/e203/dilithium/ 与 icb2apb.v 零改动（diff 可查）；
  e203_soc_top.v 仅 2 行时钟引脚修复（经批准后执行，diff 存档）；
  编译/objcopy/link.ld 参数零改动。
- 波形截图：本流程为纯 batch，未开 GUI。wave_full_lv5.wdb 已含全部关键信号，
  在 Vivado GUI 中 `open_wave_database` 即可截取 wptr 灌满、done 跳变、TEST_PASS 时刻。
- tb_top.v 的 DIL_PROBE 探针为纯 $display，可留可去；去掉不影响功能。
