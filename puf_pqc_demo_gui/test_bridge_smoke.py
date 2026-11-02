# -*- coding: utf-8 -*-
"""
test_bridge_smoke.py — 文件信箱桥冒烟测试（stage 1 验收，硬判据）

流程：清空信箱 → （需要时）精化 → 启动常驻 xsim → 等 boot banner →
HELP ×2（第一发吸收幻影字节，第二发应回干净 cmds:）→
FW <内置2KB固件 4096hex> → 等 RES FW SHA3 <64hex> 并与 test_kat.py 硬编码
期望值逐字符比对 → QUIT → 确认 xsim 进程退出。
打印 PASS/FAIL 与各阶段 wall-clock 计时。退出码 0=PASS。
"""
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from xsim_link import XsimLink  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 与 test_kat.py 对拍值一致（hashlib.sha3_256(bytes(range(256))*8)，硬件实测见
# sim_logs/sim_scenA_dev0.log）
EXPECTED_FW_SHA3 = "498cd3cc87a77b907debb761a2e6f59ed9edeaefc74f2c9c5c5f3b62f64c4aa1"

fails = 0


def check(name, ok, detail=""):
    global fails
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        fails += 1


def log_cb(tag, text):
    print(f"    [{tag}] {text}")


def main():
    t_start = time.time()

    def lap(t0):
        return f"{time.time() - t0:.1f}s"

    link = XsimLink(log_cb=log_cb)
    print("=" * 72)
    print("test_bridge_smoke.py — xsim 文件信箱桥冒烟测试")
    print("=" * 72)

    # 1) 信箱复位 + 精化
    link.reset_bridge()
    t0 = time.time()
    check("elab: tb_top_link_behav 快照就绪", link.elaborate(), lap(t0))

    # 2) 启动 xsim 并等 boot banner
    boot_s = help_s = fw_s = quit_s = "n/a"
    t0 = time.time()
    link.start()
    try:
        banner = link.wait_boot()
        boot_s = lap(t0)
        check("boot: 收到固件 banner", True, f"{banner.strip()!r}  ({boot_s})")

        # 3) 2×HELP 同步前导
        t0 = time.time()
        link.send("HELP")
        try:
            link.wait_line(timeout=120)          # HELP#1：吸收幻影字节，内容不定
        except TimeoutError:
            pass                                  # 首帧被吞也算已知行为
        link.send("HELP")
        help_line = link.wait_for("cmds:", timeout=120)
        help_s = lap(t0)
        check("HELP×2: 第二发回干净帮助文本", "cmds:" in help_line, f"({help_s})")

        # 4) FW 2KB（0x00..0xFF 循环×8 = 4096 hex）→ RES FW SHA3
        fw = bytes(range(256)) * 8
        t0 = time.time()
        link.send("FW " + fw.hex())
        fw_line = link.wait_for("RES FW SHA3 ", timeout=1800)
        fw_s = lap(t0)
        digest = fw_line.split()[-1].strip().lower()
        check("FW: RES FW SHA3 收到 64hex", len(digest) == 64 and
              all(c in "0123456789abcdef" for c in digest), digest[:16] + "…")
        check("FW: 摘要 == test_kat 硬编码期望值", digest == EXPECTED_FW_SHA3,
              f"got {digest}")
        print(f"    [LINK] expected {EXPECTED_FW_SHA3}")
        print(f"    [LINK] observed {digest}")
    finally:
        # 5) QUIT 并确认进程退出
        t0 = time.time()
        link.quit()
        quit_s = lap(t0)
        check("QUIT: xsim 进程自行退出", link.proc is None, f"({quit_s})")

    print("-" * 72)
    print(f"计时：boot={boot_s}  HELP×2={help_s}  FW={fw_s}  quit={quit_s}  "
          f"total={time.time() - t_start:.1f}s")
    print(f"总计：{'PASS — 全部通过' if fails == 0 else f'FAIL — {fails} 项失败'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
