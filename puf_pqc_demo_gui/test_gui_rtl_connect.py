# -*- coding: utf-8 -*-
"""test_gui_rtl_connect.py — RTL 后端 GUI 点击路径冒烟（offscreen）

走真实 main.py 界面逻辑：选「RTL 仿真 (xsim 全链路)」→ 断言 COM 变灰 /
DEV 锁 DEV0 → 点「连接」（Worker 线程 open+2×HELP sync）→ 经 GUI 的
_run/Worker 机制再发一轮 sync 作廉价往返证明 → 点「断开」（QUIT 收尸）→
断言无残留 xsim.exe/xsimk.exe。不跑 FW/SIGN（那走 test_link_e2e.py）。
预计 ~2-3 分钟。退出码 0=PASS。
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
from xsim_link import find_bridge_sims

fails = 0


def check(name, ok, detail=""):
    global fails
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""),
          flush=True)
    if not ok:
        fails += 1


app = QApplication([])
errors = []
# offscreen 下 QMessageBox.critical 会阻塞事件循环——记录后空调用
QMessageBox.critical = staticmethod(lambda *a, **k: errors.append(str(a[2] if len(a) > 2 else a)))
QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.information = staticmethod(lambda *a, **k: None)

w = main.MainWindow(fast=True)
state = {"phase": 0, "t0": time.time(), "t_conn": None, "t_rt": None}

OVERALL_S = 300          # 连接+sync 预算（快照已精化；正常 ~30s）


def tick():
    if w.worker is not None and w.worker.isRunning():
        return
    if errors:
        check("无 GUI 错误弹窗", False, errors[0][:200])
        app.quit()
        return
    p = state["phase"]
    if p == 0:
        # 1) 选 RTL 单选 → 控件联动
        w.rb_xsim.setChecked(True)
        app.processEvents()
        check("COM 下拉+刷新按钮变灰",
              not w.cmb_port.isEnabled() and not w.btn_ref.isEnabled())
        check("DEV 下拉锁定 DEV0 且变灰",
              w.cmb_dev.currentIndex() == 0 and not w.cmb_dev.isEnabled(),
              w.cmb_dev.toolTip())
        # 2) 点「连接」
        state["t_conn"] = time.time()
        w.btn_conn.click()
        check("连接后后端为 XsimBackend",
              w.backend is not None and w.backend.__class__.__name__ == "XsimBackend")
        state["phase"] = 1
    elif p == 1:
        # 3) 连接 worker 已结束：看日志里 cmds:（2×HELP 同步前导完成）
        logtxt = w.ed_log.toPlainText()
        ok = "cmds:" in logtxt
        check("连接+2×HELP sync 完成（日志见 cmds:）", ok,
              f"{time.time() - state['t_conn']:.1f}s")
        if not ok:
            app.quit(); return
        # 4) 廉价往返：经 GUI _run/Worker 机制再跑一轮 sync（HELP×2 → cmds:）
        state["t_rt"] = time.time()
        def fn(wk):
            return w.backend.sync()
        w._run(fn, busy="GUI 往返探针 sync#2",
               on_done=lambda line: state.update(rt_line=line))
        state["phase"] = 2
    elif p == 2:
        line = state.get("rt_line") or ""
        check("GUI Worker→XsimBackend→xsim 往返（HELP×2 → cmds:）",
              "cmds:" in line, f"{time.time() - state['t_rt']:.1f}s")
        # 5) 点「断开」（QUIT 收尸）
        t = time.time()
        w.btn_conn.click()
        check("断开无异常", w.backend is None, f"{time.time() - t:.1f}s")
        state["phase"] = 3
        QTimer.singleShot(3000, app.quit)   # 留 3s 等进程退出
    elif p == 3:
        pass


t = QTimer(); t.timeout.connect(tick); t.start(200)
QTimer.singleShot(OVERALL_S * 1000, app.quit)
app.exec_()

leftover = find_bridge_sims()
check("无残留 xsim 进程（xsim.exe/xsimk.exe）", not leftover, str(leftover))
check("走完全部阶段（未在 300s 预算内卡死）", state["phase"] >= 3,
      f"停在 phase={state['phase']}")
w.close()   # closeEvent：backend=None 路径也应无异常
print(f"总计：{'PASS' if fails == 0 else f'FAIL — {fails} 项失败'}  "
      f"总耗时 {time.time() - state['t0']:.1f}s", flush=True)
sys.exit(1 if fails else 0)
