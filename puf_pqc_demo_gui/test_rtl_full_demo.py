# -*- coding: utf-8 -*-
"""test_rtl_full_demo.py — 端到端验收：真实 GUI 一键演示路径 + 真实 xsim 全链路。

offscreen 驱动真实 MainWindow：选 RTL → 连接 → 一键演示（FW→CHAL→PUBK/PRIV→SIGN→VER）
→ 断言 0=PASS、摘要=P189 金样、PUBK 前缀命中。全程约 41 分钟。退出码 0=PASS。
"""
import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QTimer
import main

app = QApplication([])
QMessageBox.critical = staticmethod(lambda *a, **k: print("MSGBOX_ERR:", a[2] if len(a) > 2 else a, flush=True))
QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.information = staticmethod(lambda *a, **k: None)

w = main.MainWindow(fast=True)          # 不 force_sim → 按 radio 走真实 RTL
state = {"phase": 0, "t0": time.time()}


def tick():
    if w.worker is not None and w.worker.isRunning():
        return
    p = state["phase"]
    if p == 0:
        w.rb_xsim.setChecked(True)
        w.btn_conn.click()
        state["phase"] = 1
    elif p == 1:
        if "cmds:" not in w.ed_log.toPlainText():
            return
        print(f"[{time.time() - state['t0']:.0f}s] RTL 连接成功，开始一键演示", flush=True)
        w._demo()
        state["phase"] = 2
    elif p == 2:
        if w.lbl_verdict.text() == "—":
            return
        el = time.time() - state["t0"]
        ok = True
        ok &= w.lbl_verdict.text() == "0 = PASS"
        ok &= w.ed_sha.toPlainText().startswith("498cd3cc")
        ok &= w.ed_pk.toPlainText().startswith("ba5fa313ffba9519")
        print(f"[{el:.0f}s] verdict={w.lbl_verdict.text()} sha={w.ed_sha.toPlainText()[:16]} "
              f"pk={w.ed_pk.toPlainText()[:16]}", flush=True)
        print("RTL FULL DEMO:", "PASS" if ok else "FAIL", flush=True)
        w.btn_conn.click()               # 断开，优雅收尸
        state["phase"] = 3
        state["ok"] = ok
        QTimer.singleShot(5000, app.quit)


t = QTimer(); t.timeout.connect(tick); t.start(500)
QTimer.singleShot(5400000, lambda: (w.close(), app.quit()))     # 90 min 兜底（走 closeEvent 收尸）
app.exec_()
sys.exit(0 if state.get("ok") else 1)
