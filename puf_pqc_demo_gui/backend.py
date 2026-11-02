# -*- coding: utf-8 -*-
"""
backend.py — 帧层后端：SimBackend（全仿真）与 SerialBackend（真实串口，上板阶段）

帧格式与 D:\\FPGA\\sim_logs\\UART_PROTOCOL.md 一字不差；命令语义与
D:\\FPGA\\Dilithium-master\\main_demo.c 逐命令对齐（strstr 容错、定长 hex 校验、
<3B 碎帧丢弃、RES UNKNOWN CMD、0=PASS/1=FAIL、2×HELP 同步前导）。

签名线上格式（与硬件 SIG/VER 帧一致）：z(2304B) | h(84B+4B零填充) | c~(32B) = 2424B；
dilithium-py 库格式：c~ | z | h (2420B)，两者在本模块转换。
"""
import os, sys, time, random, hashlib, subprocess

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
from dilithium_py.dilithium.default_parameters import Dilithium2  # noqa: E402

DEVICE_CONSTS = {"DEV0": b"\xa5" * 32, "DEV1": b"\x5a" * 32}
DEFAULT_CHAL = bytes(range(32))                      # 000102…1f
HELP_TEXT = ("cmds: CHAL <64hex> | SEED <64hex> | FW <4096hex> | SIGN | "
             "VER <hex> | PUBK | PRIV | WIPE | DONE | HELP")
BANNER = "E203+Dilithium+PUF demo ready. HELP for cmds."

Z_LEN, H_LEN, H_PAD, C_LEN = 2304, 84, 4, 32         # lv2 段长（字节）
WIRE_SIG_LEN = Z_LEN + H_LEN + H_PAD + C_LEN         # 2424B = 4848hex


def builtin_firmware():
    """内置 2KB 固件：0x00~0xFF 循环"""
    return bytes(range(256)) * 8


def puf_response(chal32, dev):
    """PUF 行为模型：R = SHAKE-256(C ‖ DEVICE_CONST) —— 不是真芯片"""
    return hashlib.shake_256(chal32 + DEVICE_CONSTS[dev]).digest(32)


def keygen_from_seed(seed32):
    d = Dilithium2
    d.random_bytes = lambda n, s=seed32: s[:n]       # 确定性 keygen（同官方 KAT 流程）
    return d.keygen()


def sig_lib_to_wire(sig2420):
    """库格式 c~|z|h → 线上格式 z|h(pad88)|c~"""
    c, z, h = sig2420[:C_LEN], sig2420[C_LEN:C_LEN + Z_LEN], sig2420[C_LEN + Z_LEN:]
    return z + h + b"\x00" * H_PAD + c


def sig_wire_to_lib(wire2424):
    z = wire2424[:Z_LEN]
    h = wire2424[Z_LEN:Z_LEN + H_LEN]                # 丢弃 4B 零填充
    c = wire2424[Z_LEN + H_LEN + H_PAD:]
    return c + z + h


class SimBackend:
    """全仿真后端：在帧层行为级复现 main_demo.c + PUF 行为模型。"""

    name = "仿真后端"

    def __init__(self, log_cb, dev="DEV0", fast=False):
        self.log = log_cb                            # log_cb(tag, text)
        self.dev = dev
        self.fast = fast                             # 截图/自测时加速
        self.key_ready = False
        self.msg_ready = False
        self.pk = self.sk = None
        self.digest = None
        self.sig_wire = None

    # ---- 内部 ----
    def _dly(self, lo=30, hi=300):
        if not self.fast:
            time.sleep(random.randint(lo, hi) / 1000.0)

    def _pc(self, frame):                            # PC→FPGA 帧（串口B）
        self.log("PC", frame if len(frame) <= 90 else frame[:80] + f"…<{len(frame)}B帧>")
        self._dly(10, 60)
        self.log("PC>", frame if len(frame) <= 90 else frame[:80] + f"…<{len(frame)}B帧>")

    def _fpga(self, line):                           # FPGA→PC 响应（串口B）
        self._dly()
        self.log("FPGA", line if len(line) <= 90 else line[:80] + f"…<{len(line)}B帧>")
        return line

    # ---- 会话 ----
    def open(self):
        self._fpga(BANNER)

    def close(self):
        pass

    def sync(self):
        """2×HELP 同步前导：第一发吸收幻影字节，第二发回干净帮助文本 = 链路锁定"""
        self.log("PC", "HELP  （同步前导 1/2，吸收幻影字节）")
        self._dly()
        self._pc("HELP")
        return self._fpga(HELP_TEXT)

    # ---- 命令（与 main_demo.c 对齐） ----
    def chal(self, chal32):
        frame = "CHAL " + chal32.hex()
        self._pc(frame)
        self.log("FPGA", "UART1 转发 → " + frame)    # 串口A
        self._dly()
        self.log("PUF", "recv C=" + chal32.hex())
        r = puf_response(chal32, self.dev)
        self.log("PUF", f"R=SHAKE256(C||DEVICE_CONST[{self.dev}])={r.hex()}")
        for _ in range(3):                           # ×3 冗余
            self._dly(5, 20)
            self.log("PUF>", "R " + r.hex())
        self.pk, self.sk = keygen_from_seed(r)
        self.key_ready = True
        self._fpga("RES KEYGEN OK (seed=PUF R)")
        return r

    def seed(self, r32):
        self._pc("SEED " + r32.hex())
        self.pk, self.sk = keygen_from_seed(r32)
        self.key_ready = True
        self._fpga("RES KEYGEN OK (seed=direct)")

    def fw(self, fw_bytes):
        if len(fw_bytes) != 2048:
            raise ValueError("固件必须为 2048B")
        self._pc("FW " + fw_bytes.hex())
        self.digest = hashlib.sha3_256(fw_bytes).digest()
        self.msg_ready = True
        self._fpga("RES FW SHA3 " + self.digest.hex())
        return self.digest

    def sign(self):
        self._pc("SIGN")
        if not (self.key_ready and self.msg_ready):
            self._fpga("RES NOT READY")
            return None
        self._dly(200, 800)                          # 拒绝采样重试，时延较大
        sig = Dilithium2.sign(self.sk, self.digest)  # 确定性签名，同硬件模式
        self.sig_wire = sig_lib_to_wire(sig)
        self._fpga("SIG " + self.sig_wire.hex())
        return self.sig_wire

    def ver(self, sig_wire):
        self._pc("VER " + sig_wire.hex())
        if not (self.key_ready and self.msg_ready):
            self._fpga("RES NOT READY")
            return None
        ok = Dilithium2.verify(self.pk, self.digest, sig_wire_to_lib(sig_wire))
        self._fpga("OK" if ok else "FAIL")           # 0=PASS / 1=FAIL
        return ok

    def pubk(self):
        self._pc("PUBK")
        if not self.key_ready:
            self._fpga("RES NOT READY")
            return None
        self._fpga("PUBK " + self.pk.hex())
        return self.pk

    def priv(self):
        self._pc("PRIV")
        if not self.key_ready:
            self._fpga("RES NOT READY")
            return None
        self._fpga("PRIV " + self.sk.hex())
        return self.sk

    def wipe(self):
        self._pc("WIPE")
        self.sk = None
        self.key_ready = False
        self._fpga("RES WIPED")

    def raw(self, line):
        """原始行注入（协议 v2 容错演示：strstr 定位 + 定长 hex 校验 + <3B 丢弃）"""
        self.log("PC>", line)
        if len(line) < 3:
            self.log("FPGA", "<碎帧静默丢弃>")
            return
        for cmd, n in (("CHAL ", 64), ("SEED ", 64), ("FW ", 4096), ("VER ", 4848)):
            p = line.find(cmd)
            if p >= 0 and all(ch in "0123456789abcdefABCDEF" for ch in line[p + len(cmd):p + len(cmd) + n]):
                self.log("FPGA", "<已定位有效命令，走正常命令路径>")
                return
        for cmd in ("SIGN", "PUBK", "PRIV", "WIPE", "DONE", "HELP"):
            if cmd in line:
                self.log("FPGA", "<已定位有效命令，走正常命令路径>")
                return
        self._fpga(f"RES UNKNOWN CMD n={len(line):02x} head=" +
                   "".join(f"{b:02x}" for b in line.encode()[:8]))


class SerialBackend:
    """真实串口后端（上板阶段使用）：115200 8N1，自动 2×HELP 同步前导。

    真板上 PC 只见串口B（UART0）；串口A（E203↔PUF）由固件转发，PC 侧不可观测。
    PUF 为真实芯片时其行为由芯片决定，本类只做帧收发。
    """

    name = "真实串口"

    def __init__(self, log_cb, port, timeout=10.0, baud=115200):
        import serial
        self.log = log_cb
        self.ser = serial.Serial(port, baud, bytesize=8, parity="N",
                                 stopbits=1, timeout=timeout)
        self.dev = None
        self._aborted = False

    def abort(self):
        """用户中途终止：置标志并关串口，_recv 循环立即抛错退出。"""
        self._aborted = True
        try:
            self.ser.close()
        except Exception:
            pass

    @staticmethod
    def list_ports():
        from serial.tools import list_ports
        return [p.device for p in list_ports.comports()]

    def _send(self, frame):
        self.log("PC", frame if len(frame) <= 90 else frame[:80] + f"…<{len(frame)}B帧>")
        self.ser.write(frame.encode() + b"\r\n")

    def _recv(self, prefixes, timeout=30.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self._aborted:
                raise RuntimeError("用户终止：串口操作已被中止")
            try:
                raw = self.ser.readline()
            except Exception as e:
                if self._aborted:
                    raise RuntimeError("用户终止：串口操作已被中止")
                raise e
            if not raw:
                continue
            line = raw.decode(errors="replace").strip()
            if not line:
                continue
            self.log("FPGA", line if len(line) <= 90 else line[:80] + f"…<{len(line)}B帧>")
            for p in prefixes:
                if p in line:                        # strstr 容错（协议 v2）
                    return line[line.find(p):]
        raise TimeoutError("串口响应超时: " + "/".join(prefixes))

    def open(self):
        self._recv([BANNER], timeout=5) if False else None

    def close(self):
        self.ser.close()

    def sync(self):
        self._send("HELP")                           # 前导 1/2
        time.sleep(0.2)
        self.ser.reset_input_buffer()
        self._send("HELP")                           # 前导 2/2
        return self._recv(["cmds:"])

    def chal(self, chal32):
        self._send("CHAL " + chal32.hex())
        self._recv(["RES KEYGEN OK", "RES PUF TIMEOUT"])
        return None                                  # R 在串口A，PC 不可见

    def seed(self, r32):
        self._send("SEED " + r32.hex())
        self._recv(["RES KEYGEN OK"])

    def fw(self, fw_bytes):
        self._send("FW " + fw_bytes.hex())
        line = self._recv(["RES FW SHA3 "])
        return bytes.fromhex(line.split()[-1])

    def sign(self):
        self._send("SIGN")
        line = self._recv(["SIG ", "RES NOT READY"], timeout=120)
        if "SIG " not in line:
            return None
        return bytes.fromhex(line.split("SIG ", 1)[1])

    def ver(self, sig_wire):
        self._send("VER " + sig_wire.hex())
        line = self._recv(["OK", "FAIL", "RES NOT READY"], timeout=120)
        if "OK" in line:
            return True
        if "FAIL" in line:
            return False
        return None

    def pubk(self):
        self._send("PUBK")
        line = self._recv(["PUBK ", "RES NOT READY"])
        return bytes.fromhex(line.split("PUBK ", 1)[1]) if "PUBK " in line else None

    def priv(self):
        self._send("PRIV")
        line = self._recv(["PRIV ", "RES NOT READY"])
        return bytes.fromhex(line.split("PRIV ", 1)[1]) if "PRIV " in line else None

    def wipe(self):
        self._send("WIPE")
        self._recv(["RES WIPED"])

    def raw(self, line):
        self._send(line)


class XsimBackend:
    """RTL 仿真后端：经文件信箱桥驱动常驻 Vivado xsim（E203+Dilithium RTL + PUF 行为模型）。

    与 Sim/Serial 后端同一套鸭子类型 API；帧格式与 UART_PROTOCOL.md 一字不差，
    线上跑的是真实 RTL（tb_top_link.v）。传输层为 xsim_link.XsimLink
    （cmd_%04d.req/.ack + rsp.txt，详见 docs/DEVELOPER.md）。

    ★慢是正常现象：实测仿真速率 ~7-12µs sim/s wall——FW 入库 ≈19 分钟、
      SIGN ≈5-10 分钟、VER ≈12 分钟、全流程 ≈45-60 分钟（见 README 时延表）。
    ★当前固定 DEV0（tb_top_link.v 内 DEVICE_CONST=0xA5×32）。
    """

    name = "RTL 仿真 (xsim 全链路)"

    # 各命令 wall 超时（按 stage-1 实测值 + 2 倍负载裕量；机器繁忙时仿真会慢一倍以上）
    T_BOOT, T_HELP, T_CHAL = 600, 120, 600
    T_FW, T_SIGN, T_VER = 3600, 3000, 3000
    T_PUBK, T_PRIV, T_WIPE = 1200, 1800, 120

    def __init__(self, log_cb):
        from xsim_link import XsimLink
        self.log = log_cb
        self.link = XsimLink(log_cb=log_cb)
        self.dev = "DEV0"                        # 固定，见 chal()

    # ---- 内部 ----
    def _inject(self, frame, note=""):
        """发帧并给出长注入的人性化日志（ack = 注入完成）。"""
        self.link.assert_alive()
        n = len(frame) + 2
        if n > 200:
            self.log("LINK", f"注入中 ({n}B, 空闲机器约 {n * 0.054 / 60:.0f} 分钟；"
                             f"负载高时更久，xsim 在算就属正常)…"
                             + (f" [{note}]" if note else ""))
        cid = self.link.send(frame)
        if n > 200:
            self.log("LINK", f"cmd_{cid:04d} 注入完成，等待 RTL 计算…"
                             + (f" [{note}]" if note else ""))

    def _puf_r_from_console(self):
        """从 xsim console log 抓最近一次 [PUF] R=…（串口A 流量 PC 本不可见，
        RTL 模式下借仿真日志取回 R 用于界面展示）。
        console 里 tb 轮询 WARNING 可能与响应行交叠（如 "PUB"+WARNING+"K"），
        先用正则剥掉 WARNING 片段再按行扫描。"""
        import re
        from xsim_link import CONSOLE_LOG
        marker = "[PUF] R=SHAKE256(C||DEVICE_CONST)="
        warn_re = re.compile(r"WARNING: file \S+ could not be opened\n?")
        try:
            with open(CONSOLE_LOG, "r", errors="replace") as f:
                text = warn_re.sub("", f.read()[-20000:])
            for line in reversed(text.splitlines()):
                p = line.find(marker)
                if p >= 0:
                    h = line[p + len(marker):].strip()
                    if len(h) == 64 and all(c in "0123456789abcdef" for c in h):
                        return bytes.fromhex(h)
        except OSError:
            pass
        return None

    # ---- 会话 ----
    def open(self):
        from xsim_link import (kill_zombie_xsim, find_bridge_sims, RUN_LINK_SH,
                               _find_bash, XSIM_DIR, CONSOLE_LOG)
        # 路径自检：目录被改名/移动时给出明确中文错误，而不是怪异行为
        tb = r"D:\FPGA\e203_hbirdv2-master\tb\tb_top_link.v"
        if not os.path.isfile(tb):
            raise RuntimeError(
                "RTL 桥 testbench 缺失：期望 " + tb + "\n"
                "e203 源码目录是否被改名/移动？请恢复原名 "
                "D:\\FPGA\\e203_hbirdv2-master 或同步修改 run_link.sh。")
        if not os.path.isdir(XSIM_DIR):
            raise RuntimeError("xsim 工作目录缺失：" + XSIM_DIR)
        if not os.path.isfile(r"D:\Xilinx\Vivado\2019.2\bin\xsim.bat"):
            raise RuntimeError("Vivado 2019.2 未找到：期望 "
                               "D:\\Xilinx\\Vivado\\2019.2\\bin\\xsim.bat")
        killed = kill_zombie_xsim(lambda m: self.log("LINK", m))
        if killed:
            self.log("LINK", f"已清理 {len(killed)} 个残留 xsim 进程")
        self.link.reset_bridge()
        try:
            os.remove(CONSOLE_LOG)   # 删掉上次会话的 console，防止报错时误贴残留
        except OSError:
            pass
        if not self.link.is_elaborated():
            self.log("LINK", "首次使用需编译 tb_top_link（xvlog+xelab，约 1 分钟）…")
            p = subprocess.Popen([_find_bash(), RUN_LINK_SH, "--elab-only"],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, errors="replace")
            for line in p.stdout:
                line = line.rstrip()
                if line:
                    self.log("LINK", line[:120])
            if p.wait() != 0 or not self.link.is_elaborated():
                raise RuntimeError("tb_top_link 编译/精化失败，详见上方日志与 "
                                   "D:\\FPGA\\sim_logs\\elaborate_link.log")
        self.link.start()
        self.log("LINK", "xsim 启动中，等待固件 boot banner（约 5 秒）…")
        banner = self.link.wait_boot(self.T_BOOT)
        self.log("FPGA", banner)
        pids = find_bridge_sims()
        if not pids:
            raise RuntimeError(
                "RTL 拉起核验失败：boot banner 已出现，但系统里找不到 "
                "tb_top_link 的 xsim 进程。仿真没有真实运行，连接中止"
                "（宁可报错，绝不给出无真实来源的结果）。")
        self.xsim_pids = pids
        self.log("LINK", f"进程核验通过：xsim 真实运行中 pid={pids}"
                         "（任务管理器可见 xsim.exe / xsimk.exe）")

    def close(self):
        """QUIT + 收尸；幂等，崩溃后调用安全。"""
        try:
            self.link.quit()
        except Exception as e:
            self.log("LINK", f"close 异常（忽略）: {e!r}")

    def abort(self):
        """用户中途终止：立即杀 xsim 进程树并清信箱残留（不等 QUIT）。"""
        try:
            self.link.abort()
        except Exception as e:
            self.log("LINK", f"abort 异常（忽略）: {e!r}")

    def sync(self):
        self.log("PC", "HELP  （同步前导 1/2，吸收幻影字节）")
        self.link.send("HELP")
        try:
            self.link.wait_line(self.T_HELP)
        except TimeoutError:
            self.log("FPGA", "<HELP#1 无响应（幻影字节期），继续>")
        self.link.send("HELP")
        return self.link.wait_for("cmds:", self.T_HELP)

    # ---- 命令（与 main_demo.c 对齐） ----
    def chal(self, chal32):
        if self.dev != "DEV0":
            raise RuntimeError("RTL 后端当前固定 DEV0（DEVICE_CONST=0xA5×32），"
                               "DEV1 请改用仿真后端")
        self._inject("CHAL " + chal32.hex())
        line = self.link.wait_for_any(["RES KEYGEN OK", "RES PUF TIMEOUT"], self.T_CHAL)
        if "RES KEYGEN OK" not in line:
            raise RuntimeError("CHAL 失败: " + line)
        r = self._puf_r_from_console()
        if r:
            self.log("PUF", "R=SHAKE256(C||DEVICE_CONST[DEV0])=" + r.hex()
                            + "（取自 xsim console 串口A 日志）")
        return r                                  # None 时 GUI 显示"串口A 不可见"

    def seed(self, r32):
        self._inject("SEED " + r32.hex())
        self.link.wait_for("RES KEYGEN OK", self.T_CHAL)

    def fw(self, fw_bytes):
        if len(fw_bytes) != 2048:
            raise ValueError("固件必须为 2048B")
        self._inject("FW " + fw_bytes.hex(), "FW 入库+SHA3，全程约 19 分钟")
        line = self.link.wait_for("RES FW SHA3 ", self.T_FW)
        return bytes.fromhex(line.split()[-1])

    def sign(self):
        self._inject("SIGN")
        line = self.link.wait_for_any(["SIG ", "RES NOT READY"], self.T_SIGN)
        if "SIG " not in line:
            return None
        return bytes.fromhex(line.split("SIG ", 1)[1])

    def ver(self, sig_wire):
        self._inject("VER " + sig_wire.hex(), "VER 验签，全程约 12 分钟")
        line = self.link.wait_for_any(["OK", "FAIL", "RES NOT READY"], self.T_VER)
        if "OK" in line:
            return True
        if "FAIL" in line:
            return False
        return None

    def pubk(self):
        self._inject("PUBK")
        line = self.link.wait_for_any(["PUBK ", "RES NOT READY"], self.T_PUBK)
        return bytes.fromhex(line.split("PUBK ", 1)[1]) if "PUBK " in line else None

    def priv(self):
        self._inject("PRIV")
        line = self.link.wait_for_any(["PRIV ", "RES NOT READY"], self.T_PRIV)
        return bytes.fromhex(line.split("PRIV ", 1)[1]) if "PRIV " in line else None

    def wipe(self):
        self._inject("WIPE")
        self.link.wait_for("RES WIPED", self.T_WIPE)

    def raw(self, line):
        self.link.send(line)
