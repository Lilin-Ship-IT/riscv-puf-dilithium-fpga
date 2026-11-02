# -*- coding: utf-8 -*-
"""
test_link_e2e.py — XsimBackend 全链路端到端验收（stage 2 硬判据）

驱动 XsimBackend 走完 GUI 一键演示的完整链路：
  open（清信箱→精化→起 xsim→boot banner）→ sync（2×HELP 前导）→
  fw（内置 2KB 固件）→ chal（默认 DEV0 挑战 0001…1f）→ pubk/priv →
  sign → ver（预期 0=PASS）。
硬比对：
  固件摘要 == test_kat 硬编码 498cd3cc…；
  PUF R == 7a472b83…1b75（DEV0 实测）；
  PUBK/PRIV == expected_hw_values.json DEV0_PUBK/DEV0_PRIV 逐字节；
  ver == True。
打印每步 wall 计时与总 PASS/FAIL。退出码 0=PASS。
预计总耗时 45~60 分钟（RTL 全链路，慢属正常）。
"""
import os
import sys
import time
import json

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from backend import XsimBackend, DEFAULT_CHAL, builtin_firmware  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EXPECTED_FW_SHA3 = "498cd3cc87a77b907debb761a2e6f59ed9edeaefc74f2c9c5c5f3b62f64c4aa1"
EXPECTED_R_DEV0 = "7a472b8311da5759b39f9618c8731a252a310d318f6dc71ca71c448f4cd31b75"

fails = 0


def check(name, ok, detail=""):
    global fails
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""),
          flush=True)
    if not ok:
        fails += 1


def log_cb(tag, text):
    print(f"    [{tag}] {text}", flush=True)


def main():
    t_start = time.time()
    steps = {}

    def lap(t0, name):
        steps[name] = time.time() - t0
        return f"{steps[name]:.1f}s"

    be = XsimBackend(log_cb)
    print("=" * 72, flush=True)
    print("test_link_e2e.py — XsimBackend 全链路端到端验收", flush=True)
    print("=" * 72, flush=True)

    try:
        t0 = time.time()
        be.open()
        check("open: boot banner", True, lap(t0, "open"))

        t0 = time.time()
        help_line = be.sync()
        check("sync: 2×HELP → cmds:", "cmds:" in help_line, lap(t0, "sync"))

        t0 = time.time()
        digest = be.fw(builtin_firmware())
        s = lap(t0, "fw")
        check("fw: 摘要 == 498cd3cc…（对拍 test_kat）", digest.hex() == EXPECTED_FW_SHA3,
              f"{digest.hex()[:16]}…  ({s})")

        t0 = time.time()
        r = be.chal(DEFAULT_CHAL)
        s = lap(t0, "chal")
        check("chal: RES KEYGEN OK", True, s)
        check("chal: R == 7a472b83…（DEV0 实测）",
              r is not None and r.hex() == EXPECTED_R_DEV0,
              (r.hex()[:16] + "…") if r else "R 未取回")

        exp = json.load(open(os.path.join(BASE, "expected_hw_values.json")))
        t0 = time.time()
        pk = be.pubk()
        s1 = lap(t0, "pubk")
        t0 = time.time()
        sk = be.priv()
        s2 = lap(t0, "priv")
        check("pubk: == expected_hw_values DEV0_PUBK（2624hex 逐字节）",
              pk is not None and pk.hex() == exp["DEV0_PUBK"],
              f"前缀 {pk.hex()[:16]}  ({s1})")
        check("priv: == expected_hw_values DEV0_PRIV（5056hex 逐字节）",
              sk is not None and sk.hex() == exp["DEV0_PRIV"],
              f"前缀 {sk.hex()[:16]}  ({s2})")

        t0 = time.time()
        sig = be.sign()
        s = lap(t0, "sign")
        check("sign: 取得 SIG 线上格式 2424B", sig is not None and len(sig) == 2424,
              f"前缀 {sig.hex()[:16]}…  ({s})" if sig else "RES NOT READY")

        t0 = time.time()
        ok = be.ver(sig)
        s = lap(t0, "ver")
        check("ver: 0=PASS", ok is True, s)
    finally:
        t0 = time.time()
        be.close()
        check("close: xsim 退出（无僵尸）", True, lap(t0, "close"))

    print("-" * 72, flush=True)
    print("分步计时：" + "  ".join(f"{k}={v:.1f}s" for k, v in steps.items()), flush=True)
    print(f"总计：{'PASS — 全链路通过' if fails == 0 else f'FAIL — {fails} 项失败'}"
          f"  总耗时 {time.time() - t_start:.1f}s", flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
