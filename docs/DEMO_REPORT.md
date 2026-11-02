# E203 + Dilithium + PUF 全链路演示系统 DEMO_REPORT

（纯行为仿真，不上板；Vivado 2019.2 xsim；所有结论以 D:\FPGA\sim_logs\ 下 log 为证）

> **PUF 声明**：本演示 PUF 为 testbench 行为级等效模型（R = SHAKE-256(C ‖ DEVICE_CONST)，
> 单向性/确定性/不可克隆性为模型假设），**真芯片未对接**，对接属后续上板阶段。
> **签名模式声明**：本实现为确定性签名（无外部 rnd，对应 FIPS 204 deterministic 模式）；
> 与官方 hedged KAT 签名向量不做逐字节判据，自测判据为 sign→verify 回路。
> **verify 结果字约定：0=PASS / 1=FAIL**（固件、协议、本报告统一）。

## 1. 系统组成与数据流

```
固件库(PC, tb激励) ─串口B(UART0)→ E203 ─串口A(UART1)→ PUF行为模型(tb, SHAKE-256)
                         │
                         ├─ 软件 SHA3-256（2KB固件→32B摘要 M）
                         └─ sysper→icb2apb→dilithium_apb→GMUCERG Dilithium核
                              keygen(R)→pk,sk   sign(sk,M)→sig   verify→0/1
```

与需求方手绘图逐框对应：①固件库发 C+2KB固件 ②串口A C→PUF→R ③串口B R 入 FPGA、
固件经软件 SHA3 求摘要（固件本身不进 Dilithium）④keygen(R) ⑤sign(sk,摘要)
⑥公钥/私钥/签名回传 + 本地 verify 回传 OK/FAIL。
**关键事实**：PUF 响应 256bit(32B) 恰好 = keygen 种子长度，R 直接作 seed。

## 2. 阶段 1：Dilithium 三模式打通（含上游内核修复）

- wrapper（dilithium_apb.v）三模式字数表 + 输出 64b→2×32b 拆字；diff: rtl/wrapper.diff。
- **GMUCERG 内核行为仿真缺陷修复（用户授权，偏离上游，上板前需复核）**：
  ① combined_top.v cstate2 复位笔误；② start_geny 组合覆盖；③ expandmask_ext.v
  ctrl_len 用陈旧 msg_bytes；④ GenY S_HOLD→S_INIT 无空拍。
  备份 rtl/core_before/，diff: rtl/core.diff（改动处带 FIX(sandbox-verified) 注释）。
- 官方 tb_sign_top 独立 xsim **15/15 通过、0 Error**（official_tb_dbg/sign/sign_full_console.log）。
- SoC 自测（固件驱动，KAT 判据）：

| 模式 | 等级 | 判据 | 结果 | log |
|---|---|---|---|---|
| keygen | lv2 | 5/5 KAT 逐字节一致 | PASS | sim_kgonly_lv2_run2.log |
| verify | lv2 | 15/15 KAT 回归 | PASS | sim_verify_regress_lv2_console.log |
| keygen+sign→verify | lv2 | KAT 比对 + 回路 0=PASS | TEST_PASS | sim_signloop_lv2.log |
| keygen+sign→verify | lv3 | 同上 | TEST_PASS | sim_signloop_lv3.log |
| keygen+sign→verify | lv5 | 同上 | TEST_PASS | sim_signloop_lv5.log |

### 各模式周期数（官方 tb，时钟周期）

| 等级 | keygen | sign（范围，随拒绝轮数） | verify |
|---|---|---|---|
| lv2 | （见官方 log） | 10945 ~ 22609 | 6582 |
| lv3 | — | 16178 ~ 113482 | 9724 |
| lv5 | — | 24846 ~ 268203 | 14635~14647 |

（keygen 官方 tb_keygen_top 未单独跑周期统计；verify 每向量恒定。）

### 资源占用

行为仿真未做综合；wrapper 缓冲 inbuf 4096×32b / outbuf 2048×32b
（lv5 keygen 输出 1856×32b 为最大占用）。上板阶段以 Vivado 综合报告补齐。

## 3. 四场景结果（阶段 3）

挑战 C = 0001…1f(32B)；固件 = 0x00~0xFF 循环 2KB；
预期摘要（Python hashlib.sha3_256）：good=498cd3cc…4aa1 / tampered=40e61a44…02e5；
预期 R（hashlib.shake_256）：DEV=0 7a472b83…1b75 / DEV=1 1cc50e31…b98b。

| 场景 | 内容 | 预期 | 结果 | log |
|---|---|---|---|---|
| A | 全回路 CHAL→PUBK/PRIV→FW→SIGN→VER | verify OK(0) | **PASS**（TEST_PASS，26.39ms sim） | sim_scenA_dev0.log |
| B | 签名篡改 1 字节(hex[100..101]) → VER | FAIL(1) | **PASS**（verify 返回 FAIL） | sim_scenB_dev0.log |
| C | 固件篡改 1 字节(fw[0]^=1) → VER | FAIL(1) | **PASS**（verify 返回 FAIL） | sim_scenC_dev0.log |
| D | 同 C，换 DEVICE_CONST(=换芯片) | 不同 R/密钥对 | **PASS**（DEV0/1 R 与 PUBK 均不同） | sim_scenD_dev0/dev1.log |

四场景关键交叉核对（全部与 Python hashlib 预算值逐字符一致）：
- 固件摘要：good=`498cd3cc…4aa1`（场景 A/C 的 RES FW SHA3）；tampered=`40e61a44…02e5`（场景 C 第二次 RES FW SHA3）；
- PUF 响应：DEV=0 R=`7a472b83…1b75`；DEV=1 R=`1cc50e31…b98b`；
- 场景 D 唯一性：DEV=0 PUBK=`ba5fa313…` vs DEV=1 PUBK=`2fed1907…`（同 C 不同芯片 → 不同密钥对）；
- 场景 B 中 tb 将 SIG hex[100..101] 两字符取反（=篡改签名 1 字节）后 verify 返回 FAIL；
- 场景 C 中固件第 0 字节 0x00→0x01（线上取证：[PC>] FW 01010203…），摘要改变后 verify 返回 FAIL。

（console 交互摘录与 [PC]/[PUF]/[FPGA] 角色时序见 UART_PROTOCOL.md §5。）

## 4. 双串口协议分析

见 UART_PROTOCOL.md（★重点交付物）：物理层参数（115200 8N1 ↔ div=2169；
仿真加速 div=15 位 64ns）、帧格式表、全链路时序图、两链路对比表、
真 PUF 对接预留、首帧幻影字节遗留问题。

## 5. PUF 模型与私钥保护说明

- PUF 模型：R = SHAKE-256(C‖DEVICE_CONST)，DEVICE_CONST 为设备指纹参数
  （tb 内定义，DEV plusarg 换值=换一颗芯片）；行为模型经 Python hashlib.shake_256
  六组向量逐字节验证（shake256_model_tb.log，含两组 PUF 场景）。
- 私钥兜底保护：sk 驻留 DTCM（kg_buf 内 k/s1/s2/t0/tr 段），WIPE 命令覆写清零
  （对应手绘图底部 PUF"私钥兜底保护"解读）。

## 6. 工程变更清单与可复现性

- 允许改动并已改：dilithium_apb.v（wrapper.diff）、combined_top.v+expandmask_ext.v
  （core.diff，用户授权）、tb_top.v（tb_stage2.diff + tb 新增 shake256_model.v）、
  Dilithium-master 软件（main.c/main_demo.c、sha3_sw.c、uart_drv.h、kat2c_kg.py）。
- 冻结零改动：dilithium-256 内核其余 RTL、icb2apb.v、e203_soc_top.v 接线、
  编译/objcopy/link.ld 参数。
- 备份：wrapper_before/、core_before/、tb_before/、tb_before_stage2/（均在 sim_logs/rtl/）。
- 仿真流程：sim_logs/run_scen.sh（手动 xvlog/xelab/xsim 三步；规避工程 prj 截断缺陷）。
- 固件编译（一字未变的任务书命令）：见各 run_scen*_cmd.log 头部。

## 7. 遗留问题

1. UART 首帧幻影字节（已规避；根因待上板验证）——详见 UART_PROTOCOL.md §7.1。
2. 手绘图"256bit 恢复/聚合"批注待与需求方确认（本演示未含）。
3. e203_sim.xpr 工程 sim_1 导出 prj 截断缺陷（tb_top.v 不参编）——已用等效手动
   流程规避，建议后续修复工程 fileset。
