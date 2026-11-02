# 维护者文档（DEVELOPER）——PUF + Dilithium 演示 GUI

> 声明：本机仿真和 RTL 仿真中的 PUF 是行为级模型（SHAKE-256），不是物理 PUF。
> 真实开发板串口链路已实测通过；当前板上未接物理 PUF，默认使用 SEED 直注。
> FPGA 设计已 FLASH 持久化，但处理器固件每次上电仍需 openocd + gdb 下载并运行。

## 1. 模块结构

```
main.py  (GUI 层, PyQt5，左侧五页导航)
   │  只与后端接口打交道：open/close/sync/chal/seed/fw/sign/ver/pubk/priv/wipe/raw
   │  所有后端调用都在 Worker(QThread) 里跑，经 pyqtSignal 回 GUI 线程
   ▼
backend.py  (帧层)
   ├── SimBackend      本机仿真：行为级复现 main_demo.c + PUF 模型 + 串口时延
   ├── SerialBackend   真实串口：pyserial 115200 8N1，2×HELP 前导，strstr 容错
   ├── XsimBackend     RTL 仿真：驱动常驻 Vivado xsim（见 §2.7），固定 DEV0
   ├── puf_response()  PUF 行为模型 R = SHAKE-256(C ‖ DEVICE_CONST)
   ├── keygen_from_seed()  确定性 keygen（替换 Dilithium2.random_bytes）
   └── sig_lib_to_wire() / sig_wire_to_lib()  签名格式转换
xsim_link.py          文件信箱桥客户端 XsimLink（无 PyQt 依赖）+ 僵尸清理
vendor/dilithium_py/  Dilithium2 纯 Python 实现（上游 GiacomoPope/dilithium-py
                      v1.4.0，MIT，LICENSE 在 vendor/LICENSE）
test_kat.py           KAT 自测 + 硬件对拍（硬判据）
test_bridge_smoke.py  桥冒烟自验（boot/HELP/FW 摘要，~20min）
test_link_e2e.py      RTL 全链路端到端验收（~45-60min，硬判据）
gui_smoke.py          GUI 层 offscreen 冒烟（仅逻辑，不抓图）
docs/make_screenshots.py / make_overview.py  截图工具（真实 Windows 桌面渲染）
```

数据流（仿真模式一键演示）：

```
GUI 按钮 → Worker 线程 → SimBackend 方法
   → log_cb(tag, text)  → pyqtSignal → 日志窗（GUI 线程加时间戳）
   → 返回值             → result 信号 → 各显示框
```

## 2. 分层设计

### 2.1 三个后端的契约

三种后端实现同一组方法签名，GUI 不区分：

| 方法 | 语义（与 main_demo.c 对齐） | 仿真返回 | 真串口返回 |
|---|---|---|---|
| `open()` | 上电横幅 | 发 `E203+Dilithium+PUF demo ready.…` | 空操作 |
| `sync()` | 2×HELP 同步前导 | 第 1 发仅记日志，第 2 发回帮助文本 | 实发两帧，清输入缓冲 |
| `chal(C:bytes32)` | CHAL→PUF→R→keygen(R) | 返回 R | 返回 None（R 在串口A，PC 不可见） |
| `seed(R)` | 旁路喂种子 | — | — |
| `fw(bytes2048)` | 入库+SHA3 | 返回 digest | 解析 `RES FW SHA3` |
| `sign()` | 对驻留摘要签名 | 返回线上格式签名 2424B | 解析 `SIG ` |
| `ver(sig2424)` | 验签 | True/False/None | True/False/None |
| `pubk()/priv()` | 取回密钥 | bytes | bytes |
| `wipe()` | 私钥清零 | — | — |
| `raw(line)` | 原始行注入（容错演示） | 模拟解析 | 实发 |

### 2.2 SimBackend 的"帧保真"

仿真不是"调库出结果"，而是逐帧复现 `main_demo.c` 的命令循环：

- 每个命令先记 `[PC]`（PC 发送）与 `[PC>]`（线上帧）两行日志，
  回包记 `[FPGA]`；CHAL 流程额外记 `[FPGA] UART1 转发`、`[PUF] recv/R=…`、
  `[PUF>] R …` ×3（对应硬件 PUF 响应 ×3 冗余容错）；
- 每个回包带 30~300ms 随机时延（sign 200~800ms，模拟拒绝采样重试），
  `fast=True` 时全部跳过（测试/截图用）；
- 状态机字段与固件同名：`key_ready / msg_ready / digest / sk`；
  未就绪时 sign/ver/pubk/priv 回 `RES NOT READY`；
- `raw()` 复现协议 v2 容错：整行 strstr 定位命令字 + 定长 hex 校验，
  <3 字节碎帧静默丢弃，其余回 `RES UNKNOWN CMD n=XX head=…`；
- `wipe()` 清零私钥并置 `key_ready=False`，与固件 WIPE 语义一致。

### 2.3 签名的两种字节格式（改代码前必读）

| 格式 | 布局 | 长度 | 用在 |
|---|---|---|---|
| 库格式 | c̃(32) ‖ z(2304) ‖ h(84) | 2420B | dilithium-py 的 sign/verify |
| 线上格式 | z(2304) ‖ h(84+4 零填充) ‖ c̃(32) | 2424B = 4848hex | `SIG`/`VER` 帧（与硬件核输出段序 z→h→c 一致，h 段按 64bit 字对齐补 4B 零） |

转换函数 `sig_lib_to_wire / sig_wire_to_lib`（backend.py 顶部）。
**任何改动必须保持 SIG 帧 4848 hex、VER 输入 4848 hex**——这是与硬件
`SIGW=606`（32bit 字）对齐的硬约束。

### 2.4 PUF 行为模型

```python
DEVICE_CONSTS = {"DEV0": b"\xa5"*32, "DEV1": b"\x5a"*32}   # backend.py
R = shake_256(C + DEVICE_CONSTS[dev]).digest(32)           # puf_response()
```

- 位置：`backend.py` 顶部；GUI 的芯片下拉只切换 `SimBackend.dev`；
- 对应硬件：tb 内 `shake256_model.v` + plusarg 换 DEV；模型假设
  （单向性/确定性/不可克隆性）属模型声明，真芯片对接时由芯片特性替代；
- 已知对拍值（`sim_logs/EXPECTED.md`）：C=0001…1f 时
  DEV0→`7a472b83…1b75`，DEV1→`1cc50e31…b98b`。

### 2.5 Dilithium vendor 与 KAT 自测

- 版本：dilithium-py **1.4.0**（PyPI wheel 解包，`vendor/dilithium_py/`），
  上游 https://github.com/GiacomoPope/dilithium-py ，MIT，`vendor/LICENSE`；
- 用的是其中的 `Dilithium2`（pre-FIPS 参数集，tr=32B，确定性 sign，
  无 ctx 字符串）——与硬件核（GMUCERG Dilithium，round-3 语义）及
  `D:\FPGA\Dilithium-master\KAT\` 官方向量一致；**不要换成 ml_dsa 包**
  （FIPS 204 最终版，tr=64B、带 ctx，与硬件不对齐）；
- 确定性 keygen 做法：`Dilithium2.random_bytes = lambda n: seed[:n]`
  （替换熵源，等价官方 KAT 流程）；sign 本身就是确定性的（无 rnd 输入）；
- 重跑自测：`python test_kat.py`（约 1s），判据：
  a) keygen 5/5 官方 KAT 逐字节；b) verify 15/15；c) 自签自验回路+负样本；
  d) 七项硬件对拍。输出写 `test_kat_output.txt`，全过 exit 0；
- `expected_hw_values.json`：DEV0 PUBK/PRIV（2624/5056 hex）与 DEV1 PUBK
  的硬件实测完整值，用正则从 `sim_scenA_dev0.log`、`run_scenD_dev1_cmd.log`
  的 `[FPGA] PUBK/PRIV` 行提取（提取脚本见第 3 轮交付记录；
  sim_logs 只读，不得修改）。

### 2.6 GUI 线程模型（main.py）
- `Worker(QThread)`：`log(tag,text)` / `step(区名)` / `result(key,value)` /
  `failed(msg)` / `finished_ok(obj)` 五个信号；
- `_run(fn, busy, on_done)` 统一入口：更新顶部“忙碌”状态、禁用已登记的操作按钮、跑 fn；
- 后端 log_cb 从 Worker 线程发出，靠 Qt 排队连接回 GUI 线程，禁止在后端
  直接碰控件；
- `_on_result` 的 key：`sha/r/pk/sk/sig/verdict`；
- 功能组高亮：`step` 信号 → `_hl()` 改 fw/puf/alg/out 对应 QGroupBox 的 QSS 边框；
- 五页由 `QStackedWidget` 承载，左侧 `nav` 与底部上一步/下一步统一切页；
- `main.py --shot`：fast 模式 + 自动演示 + `win.grab()` 存
  `demo_screenshot.png`（供答辩用图）。

### 2.7 RTL 仿真后端与文件信箱桥（XsimBackend / XsimLink / tb_top_link.v）

三层结构，线上协议零改动（UART_PROTOCOL.md 冻结），桥只是传输层：

```
GUI → XsimBackend (backend.py)          鸭子类型同 Sim/Serial；超时按实测 wall 值
      → XsimLink (xsim_link.py)         信箱读写、rsp.txt 偏移增量读、进程收尸
        → 文件信箱 D:\FPGA\sim_logs\bridge\
          → tb_top_link.v (常驻 xsim)   位bang UART0 RX；uart0_txd → rsp.txt
            → E203 SoC + Dilithium RTL + shake256_model PUF（tb 内）
```

信箱协议（目录 `bridge/`）：

| 文件 | 方向 | 语义 |
|---|---|---|
| `cmd_%04d.tmp`→`.req` | PC→tb | 一行 ASCII 帧；tmp 写好后 `os.replace` 原子改名 |
| `cmd_%04d.ack` | tb→PC | 空文件 = 该帧已**完整注入** UART0；Python 见 ack 后删 .req/.ack（Verilog 不能删文件） |
| `rsp.txt` | tb→PC | uart0_txd 原始字节流，tb 保持打开 + 行边界 `$fflush`；Python 按偏移增量读，CRLF 需归一化 |
| `QUIT` 帧 | PC→tb | tb 写 ack 后 `$finish`；空闲 100ms sim 无命令也自终止（防僵尸） |

xsim 侧编译/运行：`D:\FPGA\sim_logs\run_link.sh [--elab-only|--run-only]`，
快照 `tb_top_link_behav`（与原 `tb_top_behav` 并存）。启动方式：
`subprocess.Popen(["bash", "run_link.sh", "--run-only"])`，Vivado PATH 由
脚本内部 export。

桥接 testbench 使用独立固件镜像 `test_link.verilog`（UART0、仿真分频 15），
不与四场景 `tb_top` 使用的 `test.verilog`（当前为 UART2 板级变体）混用。重建镜像：

```bash
cd /d/FPGA/Dilithium-master
riscv-nuclei-elf-gcc -Os -march=rv32imac -mabi=ilp32 -nostdlib -ffreestanding \
  -DPC_UART_SEL=0 -T link.ld start.S main.c -o test_link_uart0.elf
riscv-nuclei-elf-objcopy -O verilog --change-addresses=-2147483648 \
  test_link_uart0.elf /d/FPGA/my_fpga/e203_sim/e203_sim.sim/sim_1/behav/xsim/test_link.verilog
bash /d/FPGA/sim_logs/run_link.sh --elab-only
```

实测要点（坑都踩过）：

- **仿真速率 ~7-12µs sim/s wall**（事件量瓶颈，与信箱轮询无关）；
  注入速率 ~54ms wall/字节（64ns/位 ×10.5 位/字节 ÷ 仿真速率）。
  各命令 wall：boot ≈5s、HELP 往返 ≈10s、CHAL+keygen ≈1min、
  PUBK ≈3min、PRIV ≈10min、FW ≈19min（注入 4min + SHA3 15min）、
  SIGN ≈5-10min、VER ≈12min。超时见 `XsimBackend.T_*` 常量；
  `XsimLink.send()` 的 ack 超时按 `max(120s, 0.1s×字节数)` 自动缩放；
- **xsim 无 `timescale 指令时**：`#N` = N ns，但 `$time` 按 ps 显示
  （日志时间戳是 ps，别误读成 ns）；Verilog 字符串 `\r` 会退化为字符 'r'
  （CRLF 一律写 `8'h0D/8'h0A`）；`buf`/`small` 是保留字；文本模式写文件
  `\n`→`\r\n`；`$fopen` 失败打 WARNING 但多次重复会被抑制；
- **Windows 进程树**：`Popen.terminate()` 只杀 cmd.exe 包装层，
  xsim.exe/xsimk.exe 会变孤儿——收尸必须 `taskkill /F /T /PID`；
  `XsimBackend.open()` 先 `kill_zombie_xsim()` 清理上次残留；
- **序号同步**：cmd 序号在 `os.replace` 时即消耗（即使 ack 超时），
  否则 tb/Python 序号错位死锁；
- chal() 的 R 值经 xsim console log（`sim_link_console.log` 的
  `[PUF] R=…` 行）取回用于界面展示——串口A 流量 PC 侧本不可见，
  这是 RTL 模式独有的读回通道；
- tb_top_link.v 固定 DEV0（DEVICE_CONST=0xA5×32）；GUI 选择 RTL 后端时
  DEV 下拉锁定 DEV0。

验收：`test_bridge_smoke.py`（~20min：boot/HELP×2/FW 摘要对拍）与
`test_link_e2e.py`（~45-60min：全链路 + pk/sk 对 expected_hw_values.json
逐字节 + verify=PASS）。

## 3. 常见修改指南

### 3.1 改串口参数（真实串口模式）

`SerialBackend.__init__`（backend.py）：`serial.Serial(port, 115200, bytesize=8,
parity="N", stopbits=1, …)`。真机波特率由固件 `uart_drv.h` 的
`UART_BAUD_DIV_HW=2169` 决定（250MHz 外设时钟），PC 侧恒为 115200；
若固件改时钟，同步改这里与 `UART_PROTOCOL.md`。

### 3.2 换/加 PUF"芯片"

`DEVICE_CONSTS` 加一项（如 `"DEV2": b"\x3c"*32`），GUI 下拉
`self.cmb_dev.addItems([...])`（main.py）加一行，`_dev()` 映射同步加。
新芯片的 R/PUBK 对拍值需先从硬件实测提取，再加进 `test_kat.py` 对拍段。

### 3.3 加一条命令

1. `SimBackend` 加同名方法：记 `[PC]/[PC>]` 帧 → 计算 → `_fpga("RES …")`；
   容错分支在 `raw()` 里登记命令字与 hex 长度；
2. `SerialBackend` 加同签名方法：`_send()` + `_recv(["响应前缀"])`；
3. GUI 加按钮 → `_run()` 里调后端；
4. 同步更新：本文件、USER_MANUAL 速查卡、`docs/make_screenshots.py`（若入镜）。
5. 帧格式一律先查 `D:\FPGA\sim_logs\UART_PROTOCOL.md`，不得自创。

### 3.4 重抓文档截图

```
python docs/make_screenshots.py   :: 五页基础图 + 状态图 → docs/screenshots/
python docs/make_overview.py      :: 五页总览拼图 00_overview_annotated.png
```

注意：必须先运行截图脚本，再生成总览；必须使用真实 Windows 桌面平台
（offscreen 在本机会丢文字，两个脚本均主动拒绝）。截图流程只用本机仿真，
不打开真实串口，也不覆盖根目录 `demo_screenshot.png`。工具内
`main.QMessageBox.information` 被替换为空操作以防弹窗阻塞（仅工具内生效）。

### 3.5 升级 vendor 的 dilithium-py

1. 解包新版 wheel 覆盖 `vendor/dilithium_py/`，更新 `vendor/LICENSE`；
2. 必跑 `python test_kat.py`——a/b/c 三条 KAT 全过才准提交；
3. 若上游 API 变动（如 `_pack_sig` 改名），只需适配 backend.py 的
   三个调用点：`keygen_from_seed`、`Dilithium2.sign`、`Dilithium2.verify`。

## 4. 已知问题与代码修改清单

### 4.1 已知问题（本轮文档化，未改代码）

| # | 问题 | 现状与处置 |
|---|---|---|
| 1 | `UART_PROTOCOL.md` 帧表写 "PRIV 10112hex" | 实测与 RECON.md 段表均为 sk=2528B=5056hex（sk 无 t1；10112 疑为 5056×2 笔误）。GUI/文档以实测为准；协议文档属冻结资产不改 |
| 2 | GUI 未提供 WIPE/DONE 独立按钮 | 协议与后端支持，当前五页界面省略；SEED 已通过“密钥方式”下拉框提供 |
| 3 | 真板当前无物理 PUF，固件需上电下载 | 真板串口链路已 PASS，默认 SEED；FPGA 设计在 FLASH 中，但 ELF 固件仍需 openocd + gdb 恢复运行，见 BOARD_OPERATION_GUIDE |
| 4 | 纯 Python Dilithium 慢于硬件 | sign 0.5~数秒（随拒绝采样轮数波动），仿真时延属刻意模拟 |
| 5 | "篡改固件再签名"语义 | 对篡改摘要签名→恢复原摘要→验签判 FAIL（等价硬件场景 C 的消息失配）；非"篡改后还能验过"的悖论，见 USER_MANUAL §5.3 |
| 6 | offscreen 平台抓图无文字 | 截图工具必须用真实 Windows 桌面平台（脚本会主动拒绝 offscreen） |
| 7 | Windows 单选框样式动画 | 程序化切换后需短暂等待再抓图（工具已处理） |
| 8 | RTL 仿真模式慢（分钟级/命令） | 固有：xsim 行为仿真 ~7-12µs sim/s wall；README/USER_MANUAL §6 已给时延说明，结果页有进度日志 |
| 9 | RTL 桥固定 DEV0 | tb_top_link.v 内 DEVICE_CONST=0xA5×32；GUI 选择 RTL 后端时锁定 DEV 下拉（tooltip 说明） |
| 10 | 强杀 python 会留僵尸 xsim | open() 时自动检测+taskkill 清理（kill_zombie_xsim）；正常退出走 QUIT |
| 11 | §4.3 冻结资产例外 | tb_top_link.v / run_link.sh / bridge/ 目录为桥接新增文件（任务要求新建，不改任何既有文件）；xsim.dir 下新增 tb_top_link_behav 快照，原 tb_top_behav 不动 |
| 12 | cmd/桌面启动时 WSL bash 抢 PATH | `shutil.which("bash")` 会先命中 `C:\Windows\System32\bash.exe`（WSL），跑不了 /d/ 路径 → rc=127 秒退、报错还贴上次会话 console 残留误导排查。已修：`_find_bash()` 排除 System32 + 逐候选探测 `/d/` 可见性；`start()` 2s 秒退检查+stderr 落盘 `bridge/xsim_stderr.log`；报错明确标注残留日志 |
| 13 | console log 中轮询 WARNING 与响应行交叠 | xsim 对每次 $fopen 扑空打 WARNING（重复会抑制，量有限），与 uart_tx 逐字符输出共享 fd 可插进行中间（"PUB"+WARNING+"K"）；rsp.txt 是独立 fd 不受影响，R 提取已先正则剥 WARNING 片段。xsim 2019.2 无按字符串抑制的 tcl 接口，不改 tb |

### 4.2 本轮代码修改清单（文档轮，仅 1 处小修）

| 文件 | 修改 | 原因 |
|---|---|---|
| `test_kat.py` | 头部加 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`（有该属性才执行） | Windows GBK 控制台运行时中文打印乱码；输出文件本即 UTF-8，此修仅影响控制台显示 |

新增（非修改）：`docs/make_screenshots.py`、`docs/make_overview.py`、
`docs/*.md`、`docs/screenshots/*.png`、`README.md` 重写为文档门面。

### 4.3 冻结资产（只读，严禁改）

`D:\FPGA\sim_logs\`（全部）、`D:\FPGA\Dilithium-master\`（全部）、
`D:\FPGA\e203_hbirdv2-master\`、`my_fpga` 工程。
