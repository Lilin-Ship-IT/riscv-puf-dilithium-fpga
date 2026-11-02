# 文档导航（DOC_INDEX）

PUF × Dilithium 可信启动演示平台 · PC 前端 GUI —— 文档、截图与事实来源索引。

> 当前声明：本机仿真和 RTL 仿真中的 PUF 是行为模型；真实开发板串口全链路已实测通过，但板上尚未接物理 PUF，当前默认 SEED 直注。FPGA 设计已实现 FLASH 持久化，处理器固件仍需每次上电经 openocd + gdb 下载并运行。

## 文档清单

| 文档 | 读者 | 内容 |
|---|---|---|
| [../README.md](../README.md) | 所有人 | 项目入口、30 秒一键演示、三种运行方式、真板现状 |
| [USER_MANUAL.md](USER_MANUAL.md) | 零背景使用者 | 新五页 GUI 控件、完整操作、结果导出、FAQ、命令速查 |
| [BOARD_OPERATION_GUIDE.md](BOARD_OPERATION_GUIDE.md) | 真板操作者 | 上电准备、openocd、gdb 固件下载、COM3 GUI、命令行 PASS 流程与故障排查 |
| [DEMO_GUIDE.md](DEMO_GUIDE.md) | 汇报人 | 10 分钟讲解、正常/篡改/DEV1 演示、真板声明与问答 |
| [RTL_MODE_GUIDE.md](RTL_MODE_GUIDE.md) | RTL 使用者/验收者 | xsim 桥接、前提、耗时和专项排障 |
| [DEVELOPER.md](DEVELOPER.md) | 维护者 | 模块结构、后端契约、协议与签名格式、维护说明 |
| [DOC_INDEX.md](DOC_INDEX.md) | — | 本文件 |

## 新五页 UI 速查

| 页面 | 核心按钮/控件 |
|---|---|
| 演示首页 | “▶ 一键开始演示” |
| 1 连接设备 | 本机仿真 / RTL 仿真 / 真实开发板；“刷新串口”“连接设备” |
| 2 固件与密钥 | “上传并计算 SHA3-256”；CHAL / SEED；“生成密钥并读取 PUBK / PRIV” |
| 3 签名与验证 | “生成签名（SIGN）”“验证签名（VERIFY）”；两种篡改演示 |
| 4 结果与日志 | PUBK / PRIV / SIG 页签；“复制全部”“导出 .hex”“保存日志” |

## 截图清单（screenshots/）

基础界面图均由 `make_screenshots.py` 在真实 Windows 桌面平台运行 GUI 抓取；总览图由 `make_overview.py` 拼接五页基础图。脚本不会覆盖根目录的 `demo_screenshot.png`。

| 文件 | 内容 | 主要引用位置 |
|---|---|---|
| 00_overview_annotated.png | 新五页界面总览拼图 | README / USER_MANUAL §3 |
| 01_home.png | 演示首页 | USER_MANUAL §3.1 |
| 02_connect.png | 连接设备页，本机仿真默认设置 | USER_MANUAL §3.2 / 总览 |
| 03_firmware_keys.png | 固件摘要、默认 CHAL 与 DEV0 密钥结果 | USER_MANUAL / DEMO_GUIDE / 总览 |
| 04_sign_verify_pass.png | 签名与验证页，0 = PASS | USER_MANUAL / DEMO_GUIDE / 总览 |
| 05_results_logs.png | 结果页 PUBK、通信日志、0 = PASS | README 外的操作与演示文档 / 总览 |
| 06_demo_running.png | 首页一键演示进行中，顶部忙碌与进度条 | USER_MANUAL §4 / DEMO_GUIDE 第一幕 |
| 07_tamper_sig_fail.png | 篡改签名后 1 = FAIL | USER_MANUAL §5.2 / DEMO_GUIDE 第三幕 |
| 08_tamper_fw_fail.png | 篡改固件流程后 1 = FAIL | USER_MANUAL §5.3 / DEMO_GUIDE 第二幕 |
| 09_dev1_keypair.png | 本机行为模型 DEV1 的不同 R 与密钥 | USER_MANUAL §5.4 / DEMO_GUIDE 第四幕 |
| 10_serial_mode.png | 真实开发板连接页，SEED 默认提示 | BOARD_OPERATION_GUIDE / USER_MANUAL §7 |
| 11_log_help_cmds.png | HELP 同步与 `cmds:` 日志 | USER_MANUAL §9 |

重新生成（Windows cmd）：

```bat
cd /d D:\FPGA\puf_pqc_demo_gui
python docs\make_screenshots.py
python docs\make_overview.py
```

必须先运行截图脚本再生成总览。两个脚本都会拒绝 offscreen 平台；本机 offscreen 会丢文字，不能用于文档图。根目录 `../demo_screenshot.png` 是主程序独立生成的一键演示完成图，README 直接引用。

## 真板事实与操作入口

- 当前串口：COM3，115200 8N1。
- 当前种子：SEED 直注；不接物理 PUF 时不使用 CHAL。
- 真板脚本：`python /d/FPGA/puf_pqc_demo_gui/board_demo_run.py`，已实测 PASS。
- openocd 配置：`nuclei-demosoc-v2.cfg`，gdb 连接 `localhost:3333`。
- 固件：`D:\FPGA\Dilithium-master\test_board_uart0.elf`，入口 `$pc=0x80000000`。
- FLASH 持久化与固件上电自动运行是两件事；后者当前仍需每次上电手动恢复。
- 具体命令和 `timeout: cmds`、COM 占用、`JTAG scan chain failed`、3333 端口、CPU halt、UNKNOWN CMD 排障均在 [BOARD_OPERATION_GUIDE.md](BOARD_OPERATION_GUIDE.md)。

## 技术事实源（只读引用）

| 来源 | 提供 |
|---|---|
| `D:\FPGA\sim_logs\UART_PROTOCOL.md` | 帧格式、命令集、容错、HELP 同步、波特率 |
| `D:\FPGA\sim_logs\EXPECTED.md` | 固件 SHA3 和行为模型 R 的预期值 |
| `D:\FPGA\sim_logs\DEMO_REPORT.md` | 既有硬件/RTL 验证场景记录 |
| `D:\FPGA\Dilithium-master\main_demo.c`、`uart_drv.h` | 命令语义和串口参数 |
| `D:\FPGA\Dilithium-master\KAT\` | Dilithium 官方向量 |
| `../expected_hw_values.json`、`../test_kat_output.txt` | 对拍值与自测输出 |
| `../board_demo_run.py` | 当前 COM3 真板 SEED 全链路脚本 |
| `../main.py` | 五页页面、实际控件文案与交互行为的直接来源 |

## 版本信息

| 项 | 值 |
|---|---|
| 文档版本 | v2.0（新五页 UI + 真板操作指南 + SEED/PUF 边界更新） |
| 日期 | 2026-10-17 |
| 对应界面 | 左侧五页导航、首页一键演示、结果页三页签 |
| 真板状态 | 串口链路已 PASS；当前无物理 PUF；FLASH 有设计，上电仍需下载固件 |
| vendor | dilithium-py 1.4.0（MIT，GiacomoPope） |
| 依赖 | Python ≥3.8、PyQt5、pyserial；截图未新增依赖 |
