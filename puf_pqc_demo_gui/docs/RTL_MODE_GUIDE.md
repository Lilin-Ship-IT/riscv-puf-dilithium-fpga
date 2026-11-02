# RTL 全链路模式 · 操作说明

GUI 直连**真实全链路 xsim RTL 仿真**（E203 固件 + Dilithium 硬件核 + `shake256_model` PUF 数学模型）的操作手册。此模式下界面点按钮，背后是真实 RTL 逐拍计算——不是 Python 数学复现。

> 桥接方式：文件信箱（`cmd_NNNN.req/.ack` + `rsp.txt`），线上帧与 `UART_PROTOCOL.md` 完全一致，协议零改动。

## 1. 三种后端速查

| | **RTL 仿真（xsim 全链路，默认）** | 硬件开发板 |
|---|---|---|
| 算什么 | **真实 RTL 逐拍推演** | 真 FPGA 板端固件与硬件核 + 真 PUF（HD13HS10K） |
| 一次完整演示 | **约 41 分钟** | 取决于板端计算和串口传输 |
| PUF / 种子 | testbench 内 PUF 行为模型，CHAL 或 SEED | 真 PUF 芯片（CHAL）或 SEED 直注 |
| 用途 | 取数/验证、向评委证明"界面背后是真硬件行为" | 真板链路演示，已实测通过 |
| 前提 | Vivado 2019.2 | FPGA 板 + JTAG + USB 串口，先「一键拉板」 |

> 界面上已移除"本机仿真"入口（Python 行为级复现，秒级）；SimBackend 代码保留，
> 供 `--shot` 截图与 offscreen 自测脚本使用。

## 2. 前提条件

1. Vivado 2019.2 已安装在 `D:\Xilinx\Vivado\2019.2`（**无需**手动配 PATH，脚本内部自动挂载）。
2. Python 环境同 Sim 模式（PyQt5；pyserial 本模式不用）。
3. Git Bash 可用（`bash` 在 PATH，或 `D:\Git\bin\bash.exe`，自动回退）。
4. 没有其他常驻 xsim 桥在运行（见 §7 Q1）。

首次连接会自动检查快照 `tb_top_link_behav`，不存在则自动编译精化（约 40 秒，结果页日志实时显示编译输出）。

## 3. 快速开始（GUI）

```bash
cd /d/FPGA/puf_pqc_demo_gui
python main.py
```

1. 左侧进入「**1 连接设备**」，点选「**全链路仿真（RTL）**」。
   - 选中后：COM 下拉与「刷新串口」自动变灰（本模式不用串口）；「3 密钥生成」页的芯片下拉锁定 **DEV0**（RTL 桥当前固定 DEV0，tooltip 有说明）。
2. 点「**连接设备**」：自动完成 启动 xsim → 等待固件 boot banner（~5s）→ **进程核验**（确认系统里存在 tb_top_link 的 xsim 进程，找不到则连接直接失败并报中文原因）→ 2×HELP 同步前导（~13s）。结果页日志出现 `cmds:` 帮助文本且状态区显示 `xsim pid=…` 即就绪——任务管理器里可看到对应 xsim.exe 进程。
   - 首次连接含编译，全程约 1 分钟；此后约 20 秒。
   - 连接后每条命令发出前都会做存活性核验（xsim 意外退出会立即中文报错，不会假装成功）。
3. 之后按页面顺序操作：「2 固件下载」上传并计算 SHA3-256 →「3 密钥生成」生成密钥并读取 PUBK/PRIV →「4 签名与验证」生成签名（SIGN）→ 验证签名（VERIFY）；或回演示首页点「**▶ 一键开始演示**」全自动。
4. 长操作期间结果页日志有进度提示：`注入中（约 N 分钟）…` → `注入完成，等待 RTL 计算…` → 结果帧。**界面不卡死**（全部跑在 Worker 线程），可以随时看日志滚动确认"正在真算"。
5. 结束：点「断开连接」或直接关窗——自动发 QUIT 并让 xsim 优雅退出（~2s，含强制收尸兜底），不留僵尸进程。

## 4. 实测耗时表（本机实测，答辩前请按此规划）

| 步骤 | 耗时 | 说明 |
|---|---|---|
| 连接（boot + 2×HELP 同步） | ~20 s（首次 +40s 编译） | |
| 固件入库 FW（2KB） | **~19 min** | 注入 4KB hex ~4 min + 硬件 SHA3 计算 ~15 min |
| PUF 挑战 CHAL（含 keygen） | ~30 s | |
| 读 PUBK / PRIV | ~2.5 / ~5 min | 大帧下行 |
| 签名 SIGN | ~5 min | |
| 验签 VER | **~9–12 min** | 注入 2424B ~4.5 min + 验签计算 |
| **一键演示全程** | **~41 min** | 实测 41.3 min 全 PASS |

> 慢是真实的代价：每一比特都是 RTL 逐拍推出的。界面已移除秒级的本机仿真入口——要快请用硬件开发板；本模式用于准备阶段取数、录制素材、向评委证明"界面背后是真硬件行为"。

## 5. 结果判读

- VERIFY 判定区 `0 = PASS`（绿）/ `1 = FAIL`（红），篡改演示按钮同 Sim 模式可用。
- 金样对拍：DEV0 的 PUBK/PRIV 与 `expected_hw_values.json` **逐字节一致**（同一 RTL 必然命中）；固件摘要与 `test_kat.py` 硬编码期望值一致。本次交付实测全部命中。
- 展示区 PUBK/PRIV/SIG 可正常导出 .hex，格式与 Sim/Serial 后端完全一致。

## 6. 命令行 / 脚本方式（不开 GUI）

```bash
# 手动编译 + 启动常驻仿真（一般不用，GUI 会自动做）
bash /d/FPGA/sim_logs/run_link.sh --elab-only   # 仅编译精化（~40s）
bash /d/FPGA/sim_logs/run_link.sh --run-only    # 常驻仿真，等信箱命令

# 冒烟测试：boot + HELP + FW 摘要对拍（~20 min）
python test_bridge_smoke.py

# 全链路验收：fw→chal→pubk/priv→sign→ver + pk/sk 对拍金样（~41 min）
python test_link_e2e.py

# GUI 点击路径快速验证：选RTL→连接→往返→断开（<1 min，不碰 FW/SIGN）
python test_gui_rtl_connect.py
```

## 7. 常见问题

**Q1 连接时报"已有常驻 xsim"/桥目录被占用？**
上一次异常退出留了僵尸进程。重连时后端会**自动检测并清理**（按 `tb_top_link` 路径匹配 + `taskkill /F /T`）；若仍失败，手动执行 `taskkill /F /IM xsim.exe` 和 `taskkill /F /IM xsimk.exe` 后再连。

**Q2 点了按钮界面"没反应"？**
看日志窗——长操作会打印"注入中（约 N 分钟）…"。RTL 模式下单条命令几分钟到十几分钟是**正常现象**，进度日志在动就是健康的。

**Q3 为什么 DEV 下拉锁死在 DEV0？**
RTL 桥 testbench 固定使用 DEV0 设备常量（`0xA5×32`）。要演示 DEV1 唯一性请用硬件开发板换真 PUF 板（换线即换板）。

**Q4 仿真放着很久没操作会自动退出吗？**
会。testbench 内置空闲看门狗（约 100ms 仿真时间 ≈ 2–3 小时无新命令），自终止防僵尸。下次点连接重新启动即可。

**Q5 可以手动删 `D:\FPGA\sim_logs\bridge\` 里的文件吗？**
仿真存活期间**不要**删 `rsp.txt`（Windows 句柄占用会失败且打乱偏移）。信箱文件 `cmd_*.req/.ack` 由协议自动生灭，无需干预。仿真退出后目录可随意清理。

**Q6 和原来的 bash 批处理仿真（run_scen.sh）冲突吗？**
不冲突。两者快照独立（`tb_top_link_behav` vs `tb_top_behav`），原四场景批处理流程一行未动，可照常使用。

## 8. 相关文件

| 文件 | 作用 |
|---|---|
| `D:\FPGA\e203_hbirdv2-master\tb\tb_top_link.v` | 桥接 testbench（信箱循环 + UART 注入/监听） |
| `D:\FPGA\sim_logs\run_link.sh` | 编译/启动脚本（`--elab-only` / `--run-only`） |
| `xsim_link.py` | Python 信箱客户端（XsimLink 类，无 GUI 依赖） |
| `backend.py` → `XsimBackend` | GUI 后端（与 Sim/Serial 同 API） |
| `D:\FPGA\sim_logs\bridge\` | 信箱运行目录（自动生灭） |
| `D:\FPGA\sim_logs\sim_link_console.log` | xsim 运行日志（排障第一现场） |
| `test_bridge_smoke.py` / `test_link_e2e.py` / `test_gui_rtl_connect.py` | 三级验证脚本 |

更深入的技术细节（信箱协议、实测速率、踩坑记录）见 [DEVELOPER.md](DEVELOPER.md) §2.7；通用 GUI 操作见 [USER_MANUAL.md](USER_MANUAL.md)。
