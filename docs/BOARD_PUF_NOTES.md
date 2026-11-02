# 真板 PUF 接入实测记录（2026-10-21 夜）

> 里程碑：**真 PUF 芯片（普安信 HD13HS10K，I2C）接入全链路并实测通过**。
> 此前所有验证中 PUF 为 tb 内 SHAKE-256 行为模型（仿真）或 SEED 直注（首次上板）；
> 本次起 CHAL 路径在真实硬件上端到端跑通。

## 1. 硬件

- 板卡：DDR200T（E203 SoC + Dilithium 加速器，flash 中为 2026-10-14 构建的 bitstream，**未改动**）
- PUF：HD13HS10K（SRAM PUF，I2C 从机，地址 0x64，3.3V），载板 `IIC_Test_Board_V1.0`（学长接好线）
- 接线：I2C1 —— gpioB[14]=SCL（封装脚 T21）/ gpioB[15]=SDA（V22）/ 3V3 / GND
- 依据：`PUF_CORE/HD13HS10K数据手册V1.5.pdf`（文本转存 `PUF_CORE/datasheet.txt`）、
  学长冒烟测试 `PUF_CORE/main.c`（hbird_sdk 版，协议已验证）

## 2. 固件改动（全部在 `Dilithium-master/`，RTL 零改动）

- 新增 `puf_i2c.h`：apb_i2c（I2C1 @ 0x1003_5000）裸机寄存器驱动。
  报文与手册/学长代码逐字节一致：`C8+00+50+32B挑战 → STOP → 等 20ms（手册≥15ms）→ C9 轮询 ACK → 读 32B R`。
  全部等待带超时上限；失败返回错误码定位失败点。
- `main_demo.c`：CHAL 分支加 `#ifdef PUF_I2C` 切换（真板走 I2C1；仿真仍走 UART1 模型，默认编译不变）；
  新增调试命令 `PON`/`POFF`（PUF_ON/OFF，C8+00+20/10）。
- 板级编译命令：

```bash
riscv-nuclei-elf-gcc.exe -Os -march=rv32imac -mabi=ilp32 -nostdlib -ffreestanding \
    -DPUF_I2C=1 -DPC_UART_SEL=0 -DUART_BAUD_DIV=UART_BAUD_DIV_HW \
    -T link.ld start.S main.c -o test_board_puf.elf
```

## 3. 实测结果（COM3，115200 8N1，串口日志截屏存作品/figures/）

| 项目 | 结果 |
|---|---|
| 挑战 `0001..1f` → R | `fa50ae9145ba5803efb9b2662ce3e401dfb71a623107b389cb1c4b91689726e9` |
| 确定性：同挑战连发两次 | R **逐位一致，零噪声 bit** |
| 唯一性：挑战首字节改 01 | R 全变 `b2926815...acc731dc` |
| keygen | `RES KEYGEN OK (seed=PUF R)` |
| FW 摘要 | `498cd3cc…f3b62f64c4aa1`，与 Python hashlib 金样逐字节一致 |
| SIGN → VER | **OK（验签通过）** |
| 与数学模型区分 | 同挑战模型预测值 `7a472b83…`（SHAKE256，EXPECTED.md），实测 `fa50ae91…` 不同 → 响应确为真芯片物理指纹 |

## 4. 现场现象与结论

1. 首次联调 CHAL 曾回 `rc=-3`（命令字 0x50 被 NACK）：PUF 处于非 ON 状态/上电初始化窗口；
   整板断电重上电后恢复。手册 §4 警告电源爬升 >100µs 可致 PUF 初始化失败，复现时再查供电。
2. `PON` 回 `RES PUF ON ERR` 但随后 CHAL 正常：芯片上电默认 PUF_ON，疑似拒绝重复使能
   （或首笔 I2C 事务毛刺），不影响使用，未深究。
3. 首帧幻影字节在真板复现（首 HELP 回 `UNKNOWN CMD head=0048454c50`，行首多 0x00）：
   与仿真 §7.1 遗留问题同源，两次 HELP 同步策略在真板同样有效。
4. openocd 一次 `all ones`（板未上电）、一次 `unable to open ftdi device`（USB 重枚举异常，
   拔插调试器恢复），均属操作层面，非设计问题。

## 5. 待办（收尾）

- [ ] 正式固件删除 CHAL 路径 `RES PUF R` 调试回显（R=密钥种子，不应上串口）
- [ ] GUI 切 CHAL 模式连真板联调（协议未变，理论零改动）
- [ ] 远期：PUF 噪声模糊提取器（helper data 可存芯片内置 EEPROM，手册 3.2 节）
