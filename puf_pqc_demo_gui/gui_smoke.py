# -*- coding: utf-8 -*-
"""gui_smoke.py — GUI 层冒烟自验（offscreen）：一键演示→PASS→篡改签名→FAIL→篡改固件→FAIL"""
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
import main

app = QApplication([])
w = main.MainWindow(fast=True, force_sim=True)
assert w.stack.count() == 5 and w.nav.count() == 5, "多页面导航缺失"
assert not w.cmb_port.isEnabled(), "RTL 仿真模式不应启用串口"
w.rb_ser.setChecked(True)
assert w.cmb_key_mode.currentIndex() == 1, "真实串口应默认 SEED 直注"
w.cmb_key_mode.setCurrentIndex(0)
w._busy(True)
w._busy(False)
assert w.cmb_key_mode.currentIndex() == 0, "手动选择 CHAL 后不应被忙闲刷新重置"
w.rb_xsim.setChecked(True)
assert w.cmb_key_mode.currentIndex() == 0, "RTL 仿真模式应默认 CHAL"
w._connect()   # fast 模式固定走 SimBackend（界面已无本机仿真入口）
state = {"phase": 0}

def tick():
    if w.worker is not None and w.worker.isRunning():
        return
    p = state["phase"]
    if p == 0:
        w._demo(); state["phase"] = 1
    elif p == 1:
        assert w.lbl_verdict.text() == "0 = PASS", w.lbl_verdict.text()
        assert w.ed_pk.toPlainText().startswith("ba5fa313ffba9519")
        assert w.ed_sha.toPlainText().startswith("498cd3cc")
        assert w.stack.currentIndex() == 4, "一键演示后应进入签名与验证页"
        w._tamper_sig(); state["phase"] = 2
    elif p == 2:
        assert w.lbl_verdict.text() == "1 = FAIL", "篡改签名未判 FAIL"
        w._tamper_fw(); state["phase"] = 3
    elif p == 3:
        assert w.lbl_verdict.text() == "1 = FAIL", "篡改固件未判 FAIL"
        print("GUI SMOKE OK: demo PASS / tamper-sig FAIL / tamper-fw FAIL")
        app.quit()

t = QTimer(); t.timeout.connect(tick); t.start(100)
QTimer.singleShot(60000, app.quit)
app.exec_()
sys.exit(0 if state["phase"] == 3 else 1)
