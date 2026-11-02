# 双串口链路协议分析报告（PC↔PUF、PC↔FPGA）

E203 + Dilithium + PUF 全链路演示系统 · 阶段 4 交付物
（串口 A 部分为行为仿真结论；**真板 PUF 已改走 I2C1 接 HD13HS10K 真芯片并实测通过
（2026-10-21），见 `BOARD_PUF_NOTES.md`**；串口 B 协议真板/仿真一致，所有结论均有
D:\FPGA\sim_logs\ 下 console log 佐证）

> **PUF 声明**：本演示中的 PUF 为 testbench 内行为级等效模型
> （R = SHAKE-256(C ‖ DEVICE_CONST)），**不是真芯片**。
> 与普安信真 PUF 芯片（256bit C/R）的对接属后续上板阶段，见 §6。

---

## 1. 物理层

| 项目 | 串口 A（PUF 通道） | 串口 B（PC↔FPGA） |
|---|---|---|
| 用途 | E203 转发挑战 C → PUF，PUF 回响应 R | PC(固件库) ↔ E203 全部命令/数据 |
| 仿真实现 | E203 perips 内 **UART1**（0x1002_3000） | E203 perips 内 **UART0**（0x1001_3000） |
| RX 注入 | tb 位bang `io_pads_gpioB_i_ival[16]`（→gpioB_in_sync[16]→uart1_rxd） | tb 位bang `io_pads_gpioA_i_ival[16]`（→gpioA_in_sync[16]→uart0_rxd） |
| TX 观测 | tb 解码 `uart1_txd`（PUF 模型接收） | tb 解码 `uart0_txd`（[FPGA] 打印+响应解析） |
| 帧格式 | 8N1（1 起始位 + 8 数据位 LSB 先 + 1 停止位，无校验） | 同左 |
| 真机参数 | 115200 8N1 | 115200 8N1 |
| 仿真参数 | div=15 → 位周期 64ns（等效 15.625Mbaud） | 同左 |

**分频说明（重要）**：本 SoC 的 apb_uart 是 16550 风格但**分频语义非标准 16×**：
位周期 = (DLL+1) 个外设时钟（RX 在 div/2 处采起始位中点后逐位采样）。
外设时钟 hfclk = 250MHz：

- 真机 115200：div = 250e6/115200 − 1 = **2169 (0x879)**，实际波特率 115207（误差 0.006%）
- 仿真加速：div = 15 → 位周期 16×4ns = **64ns**（等效 15.625Mbaud，帧格式完全一致）

固件侧两个速率由 `uart_drv.h` 的 `UART_BAUD_DIV_HW / UART_BAUD_DIV_SIM` 一键切换，
上板时换宏即可，协议层零改动。

## 2. 帧格式（应用层）

全部为 ASCII 文本帧，`\r\n` 结尾，命令字 + 空格 + hex 载荷（小写）：

| 方向 | 帧 | 载荷 | 最大帧长 |
|---|---|---|---|
| PC→FPGA | `CHAL <64hex>` | 256bit 挑战 C | 71 B |
| PC→FPGA | `SEED <64hex>` | 直接喂 R（旁路调试） | 71 B |
| PC→FPGA | `FW <4096hex>` | 2KB 固件镜像（0x00~0xFF 循环） | 4101 B |
| PC→FPGA | `SIGN` / `PUBK` / `PRIV` / `WIPE` / `DONE` / `HELP` | 无 | 6 B |
| PC→FPGA | `VER <hex>` | 签名 z‖h‖c（lv2: 2424 B = 4848 hex） | 4854 B |
| FPGA→PC | `RES KEYGEN OK (seed=...)` | — | — |
| FPGA→PC | `RES FW SHA3 <64hex>` | 固件摘要 M = SHA3-256(FW) | 80 B |
| FPGA→PC | `SIG <hex>` | 签名（lv2 4848 hex） | 4854 B |
| FPGA→PC | `PUBK <hex>` / `PRIV <hex>` | pk=(rho,t1) 2624hex / sk=(rho,k,tr,s1,s2,t0) 10112hex | 10.2 KB |
| FPGA→PC | `OK` / `FAIL` | verify 结果字 **0=PASS / 1=FAIL** | 6 B |
| FPGA→PUF（串口A） | `CHAL <64hex>` | E203 原样转发（剥离行首异常字节后） | 71 B |
| PUF→FPGA（串口A） | `R <64hex>` | 256bit 响应 R（连发 3 次冗余） | 68 B |

约定：
- **字节序**：hex 文本为自然字节序；打包进 32bit 字时高字节在前（与官方 KAT 字序一致）。
- **超时**：固件读行阻塞；PC 侧 tb 对每步响应设看门狗（10~50ms 不等，超时打印并中止）。
- **错误处理**：无法解析的帧（≥3B）回 `RES UNKNOWN CMD`；<3B 碎帧静默丢弃。
- **容错解析（协议 v2）**：接收方在整行内 strstr 定位命令字 + 定长 hex 校验，
  容忍行首幻影垃圾前缀；PUF 响应连发 3 次跨越首帧异常/耳聋期（见 §7）。
- **同步前导**：上电后 PC 先发 2×HELP 帧（第一发吸收幻影字节，第二发应返回干净
  帮助文本 = 链路锁定确认），再进入正式命令流。

## 3. 全链路时序图（场景 A，与手绘图逐框对应）

```
固件库(PC)          串口B(UART0)        E203/FPGA        串口A(UART1)      PUF(tb模型)
   │ ① CHAL C(32B) ────────────────→ │                  │                │
   │   [71B]                         │ ② 转发 CHAL ────────────────→      │
   │                                 │   [71B]                           │ R=SHAKE256
   │                                 │                                     (C‖DEV_CONST)
   │                                 │ ③ R(32B)      ←────────────────  │
   │                                 │   [68B ×3冗余]                   │
   │                                 │ ④ keygen(R) → pk,sk              │
   │ PUBK ─────────────────────────→ │ ──→ PUBK pk(1312B) [2628B]       │
   │ PRIV ─────────────────────────→ │ ──→ PRIV sk(5056B) [10118B]      │
   │ ① FW 固件(2KB) ───────────────→ │ ③ SHA3-256(FW)=M(32B)            │
   │   [4101B]                       │ ──→ RES FW SHA3 M [80B]          │
   │ SIGN ─────────────────────────→ │ ⑤ sign(sk, M) → sig              │
   │                                 │ ──→ SIG sig(2424B) [4854B]       │
   │ VER sig ──────────────────────→ │ ⑥ verify(pk, sig, M)             │
   │   [4854B]                       │ ──→ OK (0=PASS)                  │
   │ WIPE ─────────────────────────→ │ sk 段覆写清零（私钥兜底保护）     │
   │ DONE ─────────────────────────→ │ x3=1 → tb TEST_PASS              │
```

字节数标注为串口线上 ASCII 帧长；括号内为二进制载荷长度。

## 4. 两条链路协议对比

| 维度 | 串口 A（PUF 通道） | 串口 B（PC↔FPGA） |
|---|---|---|
| 角色 | E203 主，PUF 从（挑战-响应） | PC 主，E203 从（命令-响应） |
| 命令集 | 单命令 CHAL / 响应 R | 8 命令 + 7 种响应 |
| 载荷 | 定长 32B(C)/32B(R) | 0B ~ 10.2KB 变长 |
| 会话 | 无状态，每次 CHAL 独立 | 有状态（密钥对/摘要驻留，WIPE 清除） |
| 冗余 | R 连发 3 次（仿真容错） | 无（固件 strstr+hex 校验容错） |
| 流量（场景A） | ~210B | ~27KB |

手绘图对应关系：串口 A 即图中 PC↔PUF 链路（演示中由 E203 作转发代理，
物理上 E203↔PUF；逻辑上挑战 C 来自固件库）；串口 B 即 PC↔FPGA 链路。

## 5. console 完整交互记录

见 `sim_logs/sim_scen{A,B,C,D}_dev{0,1}.log`，角色前缀分行：
`[PC]` PC 发送（激励侧打印）、`[PC>]` 串口 B 线上行解码（波形取证）、
`[FPGA]` E203 UART0 响应行、`[PUF]` PUF 模型计算日志、`[PUF>]` 串口 A 线上行解码。
关键摘录（场景 D，DEV=0）：

```
[201064000] [PC] CHAL C=00010203...1c1d1e1f (32B)
[248712000] [PC>] CHAL 000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f
[295062000] [PUF] recv C=000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f
[295062000] [PUF] R=SHAKE256(C||DEVICE_CONST)=7a472b8311da5759b39f9618c8731a252a310d318f6dc71ca71c448f4cd31b75
[366070000] [PUF>] R 7a472b8311da5759b39f9618c8731a252a310d318f6dc71ca71c448f4cd31b75
[462554000] [FPGA] RES KEYGEN OK (seed=PUF R)
```

（截图位：正式答辩时按上表从 log 截取。）

场景 A 关键行（全回路，sim_scenA_dev0.log）：

```
[17735150000] [FPGA] RES FW SHA3 498cd3cc87a77b907debb761a2e6f59ed9edeaefc74f2c9c5c5f3b62f64c4aa1
[21032898000] [PC] captured SIG (4848 hex chars)
[21036432000] [PC] VER <SIG 4848 hex, 无篡改>
[26392632000] [PC] SCEN_RESULT: A PASS (verify OK as expected)
[26413858000] [FPGA] RES WIPED
```

场景 D 唯一性对比（sim_scenD_dev0.log / sim_scenD_dev1.log）：

```
DEV=0: [PUF] R=…=7a472b83…1b75   [FPGA] PUBK ba5fa313ffba9519…
DEV=1: [PUF] R=…=1cc50e31067092…b98b   [FPGA] PUBK 2fed1907ec4f0c8c…
```

## 6. 与普安信真 PUF 芯片的对接预留（上板阶段）

- 真芯片 256bit C/R 与本模型接口完全一致：`CHAL <64hex>` / `R <64hex>` 帧不变；
- 物理层换真 115200（固件 `UART_BAUD_DIV_SIM` → `UART_BAUD_DIV_HW` = 2169）；
- 串口 A 在板上为独立 UART 口线（UART1 引出至 PUF 芯片），E203 转发逻辑不变；
- 模型假设（单向性/确定性/不可克隆性）届时由真芯片特性替代，协议层无感。

## 7. 遗留问题

1. **UART 首帧幻影字节（已规避，根因待查）**：行为仿真中 UART0/UART1 在复位后
   首个接收帧出现 2~8 字节确定性畸变（[PC>] 线监听证明线上波形正确；
   U0RX/U1RX 探针证实 boot 期 GPIO 同步链复位释放产生幻影起始位 + 首帧采样相位异常、
   且存在整字节"耳聋期"）。已用同步前导 + strstr 容错 + PUF 响应×3 冗余完全规避，
   真机 115200 下是否复现需上板验证（疑与 div=15 加速档 + 该定制 uart 核行为有关）。
   证据：sim_logs/sim_u0rx_dbg.log、sim_scenD_dev0.log（U0RX/U1RX 段）。
2. **手绘图右侧 "256bit 恢复/聚合" 批注**：待与需求方确认（疑指模糊提取器密钥恢复
   与聚合签名，本演示未含）。
3. tb 的 [FPGA] 打印为整行带前缀（冻结 RTL uart_tx.v 内建 $fwrite 已提供逐字符
   实时流，逐字符重复打印会与之重叠）。
