# 基于 RISC-V 与 Dilithium 的固件可信验证系统

FPGA 创新设计竞赛参赛作品代码仓库。

基于蜂鸟 E203 RISC-V 处理器的轻量可信启动演示系统：

- **PUF**（物理不可克隆函数）生成芯片根密钥，省去非易失密钥存储；
- **Dilithium**（NIST 后量子签名标准 FIPS 204）做固件签名校验，抗量子攻击；
- 仿真阶段：全部功能在 Vivado xsim 行为级仿真验证通过（PUF 为 SHAKE-256 行为模型）；
- 真板阶段（2026-10-21）：DDR200T 开发板 + 真 PUF 芯片（HD13HS10K，I2C 接口）端到端跑通
  CHAL→PUF→keygen→FW→SHA3→SIGN→VER 全链路，验签 PASS，见 `docs/BOARD_PUF_NOTES.md`。

## 系统架构

```
PC 端（仿真中由 testbench 扮演 / 上板后是 puf_pqc_demo_gui）
   │  UART0（命令：CHAL/SEED/FW/SIGN/VER/PUBK/PRIV/WIPE/DONE/HELP）
   ▼
E203 RISC-V CPU ── 裸机固件（C 编写，Nuclei gcc 编译）
   │  LSU→BIU→sysper ICB（PPI 区）
   ▼
icb2apb.v（ICB→APB 桥）→ dilithium_apb.v（APB 寄存器外设，基址 0x1100_0000）
   │
   ▼
combined_top（Dilithium 核：keygen/sign/verify，安全级 2/3/5）

PUF 通道（仿真）：E203 ── UART1 ── tb 内 SHAKE-256 行为模型
PUF 通道（真板）：E203 ── I2C1 ── HD13HS10K 真 PUF 芯片
```

## 目录结构

| 目录 | 内容 |
|---|---|
| `e203_hbirdv2/` | E203 SoC 源码（已集成 Dilithium 加速器）。加速器 RTL 在 `rtl/e203/dilithium/`，挂载点 `rtl/e203/soc/e203_soc_top.v`，testbench 在 `tb/tb_top.v` |
| `dilithium-sw/` | Dilithium 参考实现 + 固件工作目录（`main_demo.c` 等固件、驱动 `dilithium_drv.h` / `puf_i2c.h`、链接脚本） |
| `PUF_CORE/` | PUF 芯片 I2C 冒烟测试 + HD13HS10K 数据手册文本 |
| `puf_pqc_demo_gui/` | PyQt5 上位机（双后端：软件仿真 / 串口连真板），入口 `main.py` |
| `fpga/mcu200t_board/` | 板级 Vivado 工程文件（顶层、构建脚本、时序/资源报告） |
| `fpga/project_2/` | dilithium_apb wrapper 单元测试工程 |
| `docs/` | 验证报告、UART 协议定义、金样预算值、真板实测记录 |
| `一键启动_真板演示.bat` | 真板演示一键启动脚本 |

## 验证状态（截至 2026-10-21）

- 官方 KAT 验签 **15/15 PASS**（5 组 × 安全级 2/3/5）；keygen lv2 5/5；sign→verify 回路 lv2/3/5 全 PASS
- 演示场景 A（全链路）/B（篡改签名）/C（篡改固件）/D（换芯片）全部 PASS
- tb 内 SHAKE-256 模型与 Python hashlib 逐字节一致
- **真板实测**：同挑战两次响应逐位一致（零噪声 bit）；换挑战响应全变；全链路验签 PASS。
  详见 `docs/BOARD_BUILD_NOTES.md`、`docs/BOARD_PUF_NOTES.md`

## 复现说明

固件编译（需 Nuclei RISC-V gcc 工具链）：

```bash
cd dilithium-sw
cp main_demo.c main.c
riscv-nuclei-elf-gcc -Os -march=rv32imac -mabi=ilp32 -nostdlib -ffreestanding \
    -T link.ld start.S main.c -o test.elf
riscv-nuclei-elf-objcopy -O verilog --change-addresses=-2147483648 test.elf test.verilog
```

板级固件（真 PUF）加宏：`-DPUF_I2C=1 -DPC_UART_SEL=0 -DUART_BAUD_DIV=UART_BAUD_DIV_HW`。

仿真与上板详细步骤见 `docs/` 下各报告。

## 第三方代码声明

- `e203_hbirdv2/` 基于芯来科技（Nuclei）开源的 [e203_hbirdv2](https://github.com/riscv-mcu/e203_hbirdv2) 修改，原许可证见该目录下 `LICENSE`
- Dilithium 硬件核源自 GMU CERG 的 Dilithium RTL 实现（含 4 处行为仿真级修复，FIX 标注）
- Dilithium 算法参考实现来自 [pq-crystals/dilithium](https://github.com/pq-crystals/dilithium)

## 仓库未包含的内容（体积原因）

- Vivado 仿真/综合中间产物（`*.sim/`、`*.runs/`、`*.cache/`，约 26 GB）
- NucleiStudio IDE 与 RISC-V 工具链
- e203 原始仓库中的 `riscv-tools/` 与预编译 bitstream（`prebuilt_mcs/`）
