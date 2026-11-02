# -*- coding: utf-8 -*-
"""功能校验：报告导出 + 篡改位置标注 + 深色模式切换 + 日志面板 + 信任链"""
import os, sys, tempfile, traceback
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog
from PyQt5.QtCore import QTimer
import main

app = QApplication([])
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.critical = staticmethod(lambda *a, **k: None)
w = main.MainWindow(fast=True, force_sim=True)
state = {"phase": 0}

def busy():
    return w._is_busy or (w.worker is not None and w.worker.isRunning())

def tick():
    if busy():
        return
    try:
        tick_impl()
    except Exception:
        traceback.print_exc()
        app.exit(1)

def tick_impl():
    p = state["phase"]
    if p == 0:
        w._connect(); state["phase"] = 1
    elif p == 1:
        w._demo(); state["phase"] = 2
    elif p == 2:
        if w.lbl_verdict.text() != "0 = PASS":
            return
        w._tamper_sig(); state["phase"] = 3
    elif p == 3:
        if w.lbl_verdict.text() != "1 = FAIL":
            return
        assert "篡改位置" in w.lbl_verdict_tamper.text(), w.lbl_verdict_tamper.text()
        assert "字节 #" in w.lbl_verdict_tamper.text()
        assert len(w.report) >= 3, f"报告事件过少: {len(w.report)}"
        md = os.path.join(tempfile.gettempdir(), "rep_test.md")
        csvp = os.path.join(tempfile.gettempdir(), "rep_test.csv")
        QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (md, ""))
        w._export_report("md")
        QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (csvp, ""))
        w._export_report("csv")
        assert os.path.getsize(md) > 200 and os.path.getsize(csvp) > 200
        text = open(md, encoding="utf-8").read()
        assert "验签" in text and "篡改" in text
        w._toggle_theme(); assert w.dark
        w._toggle_theme(); assert not w.dark
        w._toggle_log(); assert "展开" in w.btn_log_toggle.text()
        w._toggle_log(); assert "收起" in w.btn_log_toggle.text()
        assert any(c.states[4] == "fail" for c in w.chains)
        print("EXTENDED OK: report/tamper-pos/dark-mode/log-panel/chain", flush=True)
        app.exit(0)

t = QTimer(); t.timeout.connect(tick); t.start(100)
QTimer.singleShot(60000, lambda: app.exit(2))
sys.exit(app.exec_())
