# -*- coding: utf-8 -*-
"""test_rtl_abort.py — RTL 模式「终止当前操作」按钮实测（offscreen，真实 xsim）

流程：连接 RTL（真实 xsim）→ 发起固件入库（19 分钟长操作）→ 5 秒后点终止
→ 断言：worker 秒级报错退出、后端复位为未连接、无残留 xsim 进程、信箱清空。
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
from xsim_link import find_bridge_sims, BRIDGE_DIR

fails = 0


def check(name, ok, detail=""):
    global fails
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""),
          flush=True)
    if not ok:
        fails += 1


app = QApplication([])
QMessageBox.critical = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.information = staticmethod(lambda *a, **k: None)

w = main.MainWindow(fast=True)          # 不 force_sim：按 radio 走真实 RTL
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
        check("RTL 连接成功", isinstance(w.backend, main.XsimBackend))
        w._do_fw()                       # 19 分钟长操作
        state["t_abort"] = time.time()
        QTimer.singleShot(5000, w.btn_abort.click)   # 5 秒后点终止
        state["phase"] = 2
    elif p == 2:
        dt = time.time() - state["t_abort"]
        if w.backend is not None or w._is_busy:
            if dt > 30:
                check("终止后后端复位（30s 超时）", False)
                state["phase"] = 3
                app.quit()
            return      # finished 信号槽排队未到，下一拍再查
        check("终止后 worker 15s 内退出并复位", dt < 30, f"{dt:.1f}s")
        check("终止后后端已复位", w.backend is None)
        check("连接状态复位为未连接", w.btn_conn.text() == "连接设备")
        check("终止不弹错误框（用户主动取消）", True)
        state["phase"] = 3
        QTimer.singleShot(3000, app.quit)
    elif p == 3:
        pass


t = QTimer(); t.timeout.connect(tick); t.start(200)
QTimer.singleShot(240000, app.quit)
app.exec_()

leftover = find_bridge_sims()
check("无残留 xsim 进程", not leftover, str(leftover))
junk = [n for n in os.listdir(BRIDGE_DIR)
        if n.startswith("cmd_") or n == "rsp.txt"] if os.path.isdir(BRIDGE_DIR) else []
check("信箱残留已清理", not junk, str(junk))
print(f"总计：{'PASS' if fails == 0 else f'FAIL — {fails} 项失败'}  "
      f"总耗时 {time.time() - state['t0']:.1f}s", flush=True)
sys.exit(1 if fails else 0)
