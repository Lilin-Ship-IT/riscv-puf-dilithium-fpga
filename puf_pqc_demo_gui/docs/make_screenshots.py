# -*- coding: utf-8 -*-
"""用真实 Windows 桌面渲染 GUI，并生成文档截图。

界面已无本机仿真入口；截图用 fast 模式（内部走 SimBackend 秒级复现），
不拉起 xsim、不打开真实串口，也不覆盖项目根目录的 demo_screenshot.png。
先运行本脚本，再运行 make_overview.py。
"""
import os
import sys
import traceback

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
OUT = os.path.join(BASE, "docs", "screenshots")
os.makedirs(OUT, exist_ok=True)

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication
import main

app = QApplication([])
if app.platformName().lower() != "windows":
    raise RuntimeError("文档截图必须使用真实 Windows 桌面平台，禁止 offscreen")
app.setStyle("Fusion")
app.setStyleSheet(main.QSS)
main.QMessageBox.information = staticmethod(lambda *a, **k: None)

w = main.MainWindow(fast=True, force_sim=True)   # fast=True → _connect 固定走 SimBackend
w.show()
w.raise_()
w.activateWindow()
state = {"phase": 0, "shot_running": False, "error": None}


def running():
    return w.worker is not None and w.worker.isRunning()


def grab(name, widget=None):
    app.processEvents()
    pixmap = (widget or w).grab()
    path = os.path.join(OUT, name)
    if pixmap.isNull() or not pixmap.save(path):
        raise RuntimeError("截图保存失败: " + path)
    print("saved", name, flush=True)


def tick_impl():
    phase = state["phase"]
    if phase == 0:
        w._go_page(0)
        grab("01_home.png")
        w._go_page(1)
        grab("02_connect.png")
        w._connect()
        state["phase"] = 1
    elif phase == 1 and not running():
        assert w.backend is not None, "连接失败"
        w._go_page(0)
        w._demo()
        state["phase"] = 2
    elif phase == 2:
        if running():
            if not state["shot_running"]:
                grab("06_demo_running.png")
                state["shot_running"] = True
            return
        if not state["shot_running"]:
            return
        assert w.lbl_verdict.text() == "0 = PASS", w.lbl_verdict.text()
        w._go_page(4)
        app.processEvents()
        w.ed_log.verticalScrollBar().setValue(
            w.ed_log.verticalScrollBar().maximum())
        grab("05_results_logs.png")
        w.ed_log.verticalScrollBar().setValue(2)
        grab("11_log_help_cmds.png", w.ed_log)
        w.ed_log.verticalScrollBar().setValue(
            w.ed_log.verticalScrollBar().maximum())
        w._go_page(2)
        grab("03_firmware.png")
        w._go_page(3)
        grab("04_keys.png")
        w._go_page(4)
        grab("04_sign_verify_pass.png")
        w._tamper_sig()
        state["phase"] = 3
    elif phase == 3 and not running():
        assert w.lbl_verdict.text() == "1 = FAIL", w.lbl_verdict.text()
        w._go_page(4)
        grab("07_tamper_sig_fail.png")
        w._tamper_fw()
        state["phase"] = 4
    elif phase == 4 and not running():
        assert w.lbl_verdict.text() == "1 = FAIL", w.lbl_verdict.text()
        w._go_page(4)
        grab("08_tamper_fw_fail.png")
        w.cmb_dev.setEnabled(True)       # RTL 默认锁 DEV0，截图脚本手动解锁演示 DEV1
        w.cmb_dev.setCurrentIndex(1)
        w._go_page(3)
        w._do_keygen()
        state["phase"] = 5
    elif phase == 5 and not running():
        assert w.ed_r.text().startswith("1cc50e31"), w.ed_r.text()
        assert w.ed_pk.toPlainText().startswith("2fed1907ec4f0c8c")
        w._go_page(3)
        grab("09_dev1_keypair.png")
        w._toggle_theme()
        w._go_page(0)
        grab("15_dark_home.png")
        w._go_page(4)
        grab("16_dark_sign.png")
        w._toggle_theme()
        w._connect()
        w.rb_ser.setChecked(True)
        w._refresh_ports()
        port_index = w.cmb_port.findText("COM3")
        if port_index >= 0:
            w.cmb_port.setCurrentIndex(port_index)
        w._go_page(1)
        state["phase"] = 6
        state["wait"] = 0
    elif phase == 6:
        state["wait"] += 1
        if state["wait"] < 5:
            return
        grab("10_serial_mode.png")
        print("serial screenshot port:", w.cmb_port.currentText() or "<无串口>", flush=True)
        w.close()
        app.quit()


def tick():
    try:
        tick_impl()
    except Exception as exc:
        state["error"] = exc
        traceback.print_exc()
        app.exit(1)


def timeout():
    state["error"] = TimeoutError("截图状态机超时，phase=%s" % state["phase"])
    app.exit(2)


timer = QTimer()
timer.timeout.connect(tick)
timer.start(150)
QTimer.singleShot(180000, timeout)
rc = app.exec_()
print("done, phase =", state["phase"], flush=True)
if state["error"] is not None:
    sys.exit(1)
sys.exit(rc if rc else (0 if state["phase"] == 6 else 1))
