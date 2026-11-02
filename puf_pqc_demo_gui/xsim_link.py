# -*- coding: utf-8 -*-
"""
xsim_link.py — 文件信箱桥接客户端：Python ↔ 常驻 xsim（tb_top_link）

无 PyQt 依赖。帧格式与 UART_PROTOCOL.md / backend.SerialBackend 完全一致
（本模块只做传输层，线上协议零改动；strstr 容错解析风格同 SerialBackend._recv）。

信箱协议（目录 D:\\FPGA\\sim_logs\\bridge\\）：
  PC→tb : cmd_%04d.tmp 写好后 rename 为 cmd_%04d.req（原子），一行 ASCII 帧
  tb→PC : cmd_%04d.ack 空文件 = 该帧已完整注入 UART0；随后删除 .req/.ack
  tb→PC : rsp.txt 追加 UART0 TX 原始字节流（tb 保持打开+fflush），按偏移增量读
  特殊帧: "QUIT" → tb $finish

xsim 启动方式（Windows）：subprocess.Popen(["bash", "run_link.sh", "--run-only"], ...)
Vivado PATH 由 run_link.sh 内部 export，Python 侧无需配置环境；
bash 从 PATH 查找，找不到时回退 D:\\Git\\bin\\bash.exe。
"""
import os
import sys
import time
import shutil
import subprocess
import threading

if hasattr(sys.stdout, "reconfigure"):   # Windows GBK 控制台中文乱码修正
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BRIDGE_DIR = r"D:\FPGA\sim_logs\bridge"
XSIM_DIR = r"D:\FPGA\my_fpga\e203_sim\e203_sim.sim\sim_1\behav\xsim"
RUN_LINK_SH = r"D:\FPGA\sim_logs\run_link.sh"
SNAPSHOT_DIR = os.path.join(XSIM_DIR, "xsim.dir", "tb_top_link_behav")
CONSOLE_LOG = r"D:\FPGA\sim_logs\sim_link_console.log"

BANNER_KEY = "ready"                     # 固件 boot banner 子串（strstr 容错）

CPU_POLL_S = 15.0        # xsim CPU 采样间隔（每次 CIM 查询约 1s wall，不宜过密）
STALL_LIMIT_S = 120.0    # xsim CPU 连续无进展判卡死（慢不是错，不动才是）


_BASH_CACHE = None


def _find_bash():
    """找能识别 /d/ 路径的 MSYS/Git Bash。必须排除 WSL 的
    C:\\Windows\\System32\\bash.exe——cmd/PowerShell 启动的 Python 里它会排在
    PATH 最前，WSL 看不到 D:\\ 路径的 run_link.sh，会以 rc=127 秒退
    （xsim 根本没启动，只剩上次会话的 console 残留误导排查）。"""
    global _BASH_CACHE
    if _BASH_CACHE:
        return _BASH_CACHE
    cands = []
    w = shutil.which("bash")
    if w and "system32" not in w.lower():
        cands.append(w)
    for c in (r"D:\Git\bin\bash.exe", r"C:\Program Files\Git\bin\bash.exe",
              r"C:\Program Files (x86)\Git\bin\bash.exe"):
        if os.path.isfile(c) and c not in cands:
            cands.append(c)
    for c in cands:
        try:
            r = subprocess.run([c, "-c", "test -d /d/FPGA && echo MSYS_OK"],
                               capture_output=True, text=True, timeout=15)
            if "MSYS_OK" in r.stdout:
                _BASH_CACHE = c
                return c
        except Exception:
            continue
    raise FileNotFoundError(
        "找不到可用的 Git Bash（需要能识别 /d/ 路径的 MSYS bash；"
        "WSL 的 C:\\Windows\\System32\\bash.exe 不适用，已自动排除）。"
        "请安装 Git for Windows 或把 Git Bash 加入 PATH。")


def find_bridge_sims():
    """列出本桥接残留的 xsim 进程 PID（路径/命令行含 tb_top_link）。"""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='xsimk.exe' or Name='xsim.exe'\""
             " | Where-Object { $_.ExecutablePath -match 'tb_top_link_behav'"
             " -or $_.CommandLine -match 'tb_top_link' }"
             " | Select-Object -ExpandProperty ProcessId"],
            capture_output=True, text=True, timeout=30)
        return [int(t) for t in r.stdout.split() if t.strip().isdigit()]
    except Exception:
        return []


def bridge_cpu_time():
    """本桥接 xsim 进程累计 CPU 秒数（None=查询失败/进程不在）。
    用于区分『仿真慢但在逐拍前进』与『仿真卡死』：
    wall 超时只在后者才有意义，前者只需等。"""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='xsimk.exe' or Name='xsim.exe'\""
             " | Where-Object { $_.ExecutablePath -match 'tb_top_link_behav'"
             " -or $_.CommandLine -match 'tb_top_link' }"
             " | ForEach-Object { [int64]$_.KernelModeTime + [int64]$_.UserModeTime }"
             " | Measure-Object -Sum | Select-Object -ExpandProperty Sum"],
            capture_output=True, text=True, timeout=20)
        v = (r.stdout or "").strip()
        return float(v) / 1e7 if v else None     # Win32 时间单位 = 100ns
    except Exception:
        return None


class StallWatch:
    """注入/响应等待的活性看门狗：周期采样 xsim CPU，有进展就刷新计时。
    查询失败时退化（stalled 永不触发），由调用方的 wall 硬上限兜底。"""
    def __init__(self):
        self.last_prog = time.time()
        self._last_poll = 0.0
        self._last_cpu = None

    def stalled(self):
        now = time.time()
        if now - self._last_poll >= CPU_POLL_S:
            self._last_poll = now
            cpu = bridge_cpu_time()
            if cpu is not None:
                if self._last_cpu is None or cpu > self._last_cpu + 0.5:
                    self.last_prog = now
                self._last_cpu = cpu
        return now - self.last_prog > STALL_LIMIT_S


def kill_zombie_xsim(log=print):
    """清掉桥接快照的僵尸 xsim（上次异常退出残留）。返回被杀的 PID 列表。"""
    taskkill = shutil.which("taskkill") or os.path.join(
        os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe")
    pids = find_bridge_sims()
    for pid in pids:
        log(f"发现残留 xsim 进程 pid={pid}，taskkill /F /T 清理")
        try:
            subprocess.run([taskkill, "/F", "/T", "/PID", str(pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=30)
        except Exception:
            pass
    if pids:
        time.sleep(2)                        # 等句柄释放（rsp.txt 文件锁）
    return pids


class XsimLink:
    """常驻 xsim 仿真的文件信箱客户端。"""

    def __init__(self, bridge_dir=BRIDGE_DIR, xsim_dir=XSIM_DIR,
                 boot_timeout=600.0, ack_timeout=120.0, quit_grace=30.0,
                 log_cb=None):
        self.bridge_dir = bridge_dir
        self.xsim_dir = xsim_dir
        self.boot_timeout = boot_timeout
        self.ack_timeout = ack_timeout
        self.quit_grace = quit_grace
        self.log = log_cb or (lambda tag, text: None)
        self.proc = None
        self._cmd_id = 0
        self.cancel_event = threading.Event()   # 用户终止：所有等待循环立即抛错退出
        self._rsp_path = os.path.join(bridge_dir, "rsp.txt")
        self._rsp_off = 0                  # rsp.txt 已消费偏移
        self._rsp_buf = ""                 # 已读未匹配的行缓冲

    # ---------------- 信箱目录 ----------------
    def reset_bridge(self):
        """清空信箱目录（删除残留 .req/.ack/.tmp/rsp.txt）。必须在启动 xsim 前调用。"""
        os.makedirs(self.bridge_dir, exist_ok=True)
        for name in os.listdir(self.bridge_dir):
            if (name.startswith("cmd_") and (name.endswith(".req") or name.endswith(".ack")
                                             or name.endswith(".tmp"))) or name == "rsp.txt":
                try:
                    os.remove(os.path.join(self.bridge_dir, name))
                except OSError:
                    pass
        self._cmd_id = 0
        self._rsp_off = 0
        self._rsp_buf = ""

    # ---------------- 编译 / 启动 ----------------
    def is_elaborated(self):
        return os.path.isdir(SNAPSHOT_DIR)

    def elaborate(self, timeout=900.0):
        """编译+精化 tb_top_link（快照已存在则跳过）。返回 True=成功。"""
        if self.is_elaborated():
            return True
        self.log("LINK", "elaborating tb_top_link_behav ...")
        r = subprocess.run([_find_bash(), RUN_LINK_SH, "--elab-only"],
                           cwd=self.xsim_dir, timeout=timeout,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        ok = r.returncode == 0 and self.is_elaborated()
        if not ok:
            self.log("LINK", "elab failed:\n" + r.stdout.decode(errors="replace")[-2000:])
        return ok

    def start(self):
        """spawn xsim 运行（快照须已精化）。console 进 sim_link_console.log，
        包装链 stderr 进 bridge/xsim_stderr.log；启动后 2s 做秒退检查
        （WSL bash/路径问题会 rc=127 立刻死，必须在这里就报清楚）。"""
        if self.proc is not None:
            raise RuntimeError("xsim already running")
        self._stderr_path = os.path.join(self.bridge_dir, "xsim_stderr.log")
        self._stderr_f = open(self._stderr_path, "w", errors="replace")
        self.proc = subprocess.Popen(
            [_find_bash(), RUN_LINK_SH, "--run-only"],
            cwd=self.xsim_dir,
            stdout=subprocess.DEVNULL, stderr=self._stderr_f)
        self.log("LINK", f"xsim spawned pid={self.proc.pid}")
        time.sleep(2)
        if self.proc.poll() is not None:
            rc = self.proc.returncode
            tail = self._read_stderr_tail()
            raise RuntimeError(
                f"xsim 启动即失败（包装链 rc={rc}；127=命令未找到，"
                f"常见于 bash 找错/WSL 或 Vivado 路径问题）。\n"
                f"bash/xsim stderr:\n{tail or '(空)'}")

    # ---------------- 存活性核验 ----------------
    def assert_alive(self):
        """确认本桥 xsim 进程真实在跑，否则抛 RuntimeError。
        双保险：包装进程未退出 + 系统里找得到 tb_top_link 的 xsim/xsimk。"""
        if self.proc is None or self.proc.poll() is not None:
            raise RuntimeError("xsim 包装进程已退出（仿真未在运行）")
        if not find_bridge_sims():
            raise RuntimeError(
                "未找到 tb_top_link 的 xsim 进程——仿真没有真实拉起，"
                "已中止（宁可报错也不给出无来源的结果）")

    # ---------------- rsp.txt 增量读取 ----------------
    def _poll_rsp(self):
        """把 rsp.txt 新增内容并入行缓冲（偏移续读，容忍半截行/CRLF）。"""
        try:
            size = os.path.getsize(self._rsp_path)
        except OSError:
            return
        if size < self._rsp_off:           # rsp.txt 被重建（不应发生，reset 已清空）
            self._rsp_off = 0
        if size == self._rsp_off:
            return
        with open(self._rsp_path, "r", encoding="ascii", errors="replace",
                  newline="") as f:
            f.seek(self._rsp_off)
            data = f.read()
            self._rsp_off = f.tell()
        self._rsp_buf += data.replace("\r\n", "\n").replace("\r", "\n")

    def _next_line(self):
        """从行缓冲取一条完整行；没有则 None。"""
        p = self._rsp_buf.find("\n")
        if p < 0:
            return None
        line = self._rsp_buf[:p]
        self._rsp_buf = self._rsp_buf[p + 1:]
        return line

    def wait_for(self, prefix, timeout=60.0):
        """strstr 容错等待：逐行扫描，返回含 prefix 的行（自 prefix 起）。
        之前的行照常上交 log_cb("FPGA", ...)。超时抛 TimeoutError。"""
        t0 = time.time()
        watch = StallWatch()
        while time.time() - t0 < timeout:
            self._poll_rsp()
            while True:
                line = self._next_line()
                if line is None:
                    break
                if not line:
                    continue
                self.log("FPGA", line if len(line) <= 90 else line[:80] + f"…<{len(line)}B帧>")
                if prefix in line:         # strstr 容错（协议 v2）
                    return line[line.find(prefix):]
            self._check_alive()
            if watch.stalled():
                raise TimeoutError(
                    f"等待 {prefix!r} 期间 xsim {STALL_LIMIT_S:.0f}s 无 CPU 进展，仿真疑似卡死")
            time.sleep(0.2)
        raise TimeoutError(f"等待 {prefix!r} 超时（{timeout}s）")

    def wait_for_any(self, prefixes, timeout=60.0):
        """strstr 容错等待多个前缀之一：返回（自匹配前缀起的）行。超时抛 TimeoutError。"""
        t0 = time.time()
        watch = StallWatch()
        while time.time() - t0 < timeout:
            self._poll_rsp()
            while True:
                line = self._next_line()
                if line is None:
                    break
                if not line:
                    continue
                self.log("FPGA", line if len(line) <= 90 else line[:80] + f"…<{len(line)}B帧>")
                for p in prefixes:
                    if p in line:                # strstr 容错（协议 v2）
                        return line[line.find(p):]
            self._check_alive()
            if watch.stalled():
                raise TimeoutError(
                    f"等待 {'/'.join(prefixes)!r} 期间 xsim {STALL_LIMIT_S:.0f}s 无 CPU 进展，仿真疑似卡死")
            time.sleep(0.2)
        raise TimeoutError(f"等待 {'/'.join(prefixes)!r} 超时（{timeout}s）")

    def wait_line(self, timeout=60.0):
        """等待任意一条非空行（用于 HELP#1 同步前导这类响应内容不确定的帧）。"""
        t0 = time.time()
        watch = StallWatch()
        while time.time() - t0 < timeout:
            self._poll_rsp()
            line = self._next_line()
            if line is not None and line:
                self.log("FPGA", line if len(line) <= 90 else line[:80] + f"…<{len(line)}B帧>")
                return line
            self._check_alive()
            if watch.stalled():
                raise TimeoutError(
                    f"等待任意响应行期间 xsim {STALL_LIMIT_S:.0f}s 无 CPU 进展，仿真疑似卡死")
            time.sleep(0.2)
        raise TimeoutError(f"等待任意响应行超时（{timeout}s）")

    def wait_boot(self, timeout=None):
        """等待固件 boot banner（'E203+... ready. HELP for cmds.'）。"""
        return self.wait_for(BANNER_KEY, timeout or self.boot_timeout)

    # ---------------- 命令发送 ----------------
    def send(self, frame, ack_timeout=None):
        """原子写 cmd_%04d.req 并等待 .ack（= tb 已完整注入 UART0）。"""
        self._check_alive()
        cid = self._cmd_id
        base = os.path.join(self.bridge_dir, f"cmd_{cid:04d}")
        tmp, req, ack = base + ".tmp", base + ".req", base + ".ack"
        with open(tmp, "w", newline="\n") as f:      # 纯 \n，tb 侧也容忍 \r\n
            f.write(frame + "\n")
        os.replace(tmp, req)                         # 原子改名
        self._cmd_id += 1                            # 改名即消耗序号（即使 ack 超时也保持与 tb 同步）
        self.log("PC", frame if len(frame) <= 90 else frame[:80] + f"…<{len(frame)}B帧>")
        t0 = time.time()
        # ack = tb 完整注入 UART0。注入速率实测 ~54ms wall/字节（仿真 ~11µs sim/s wall），
        # 但机器繁忙/内存紧张时可慢数倍以上——固定 wall 超时会误杀正常仿真。
        # 双保险：硬上限放宽到 0.3s/字节 + StallWatch（仿真彻底不前进才快速失败）。
        if ack_timeout is None:
            ack_timeout = max(self.ack_timeout, 0.3 * len(frame))
        watch = StallWatch()
        last_note = t0
        while not os.path.exists(ack):
            now = time.time()
            if now - t0 > ack_timeout:
                raise TimeoutError(f"cmd_{cid:04d} ack 超时（硬上限 {ack_timeout:.0f}s）")
            if watch.stalled():
                raise TimeoutError(
                    f"cmd_{cid:04d} ack 超时：xsim 已 {STALL_LIMIT_S:.0f}s 无 CPU 进展，"
                    "仿真疑似卡死（并非单纯变慢）")
            if len(frame) > 200 and now - last_note > 60:
                last_note = now
                self.log("LINK", f"cmd_{cid:04d} 仍在注入，xsim 逐拍推进正常"
                                 f"（已等待 {now - t0:.0f}s，硬上限 {ack_timeout:.0f}s）")
            self._check_alive()
            time.sleep(0.05)
        for p in (req, ack):                         # tb 不能删文件，Python 清理
            try:
                os.remove(p)
            except OSError:
                pass
        return cid

    # ---------------- 关闭 ----------------
    def abort(self):
        """立即终止（用户取消/关窗快清）：置取消标志让等待循环立刻抛错，
        直接杀进程树（不走 QUIT 优雅流程，避免长操作期间关窗卡顿），
        并 best-effort 清理信箱残留。"""
        self.cancel_event.set()
        proc = self.proc
        self.proc = None
        if proc is not None and proc.poll() is None:
            try:
                taskkill = shutil.which("taskkill") or os.path.join(
                    os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe")
                subprocess.run([taskkill, "/F", "/T", "/PID", str(proc.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=15)
            except Exception:
                pass
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
        try:
            self._stderr_f.close()
        except (OSError, AttributeError):
            pass
        for _ in range(4):
            leftover = False
            try:
                names = os.listdir(self.bridge_dir)
            except OSError:
                break
            for name in names:
                if name.startswith("cmd_") or name == "rsp.txt":
                    try:
                        os.remove(os.path.join(self.bridge_dir, name))
                    except OSError:
                        leftover = True
            if not leftover:
                break
            time.sleep(0.3)

    def quit(self):
        """发送 QUIT，等进程退出；超时用 taskkill /T 杀整棵树
        （xsim.bat → cmd.exe → xsim.exe/xsimk.exe，Popen.terminate 只杀包装进程，
        仿真内核会变孤儿——Windows 上必须 /T 杀树）。"""
        if self.proc is None:
            return
        try:
            if self.proc.poll() is None:
                try:
                    self.send("QUIT", ack_timeout=min(self.ack_timeout, 60.0))
                except Exception as e:
                    self.log("LINK", f"QUIT 发送异常（继续收尸）: {e!r}")
                try:
                    self.proc.wait(timeout=self.quit_grace)
                except subprocess.TimeoutExpired:
                    self._kill_tree()
        finally:
            rc = self.proc.poll()
            self.log("LINK", f"xsim exited rc={rc}")
            self.proc = None
            try:
                self._stderr_f.close()
            except (OSError, AttributeError):
                pass
            # 进程死后 best-effort 清理信箱残留（重试几次，句柄释放有延迟）
            for _ in range(20):
                leftover = False
                for name in os.listdir(self.bridge_dir):
                    if name.startswith("cmd_") or name == "rsp.txt":
                        try:
                            os.remove(os.path.join(self.bridge_dir, name))
                        except OSError:
                            leftover = True
                if not leftover:
                    break
                time.sleep(0.5)

    def _kill_tree(self):
        taskkill = shutil.which("taskkill") or os.path.join(
            os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe")
        try:
            subprocess.run([taskkill, "/F", "/T", "/PID", str(self.proc.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=30)
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass

    def _read_stderr_tail(self, n=1500):
        try:
            if getattr(self, "_stderr_f", None):
                self._stderr_f.flush()
            with open(self._stderr_path, "r", errors="replace") as f:
                return f.read()[-n:]
        except (OSError, AttributeError):
            return ""

    def _check_alive(self):
        if self.cancel_event.is_set():
            raise RuntimeError("用户终止：仿真已被中止")
        if self.proc is not None and self.proc.poll() is not None:
            tail = ""
            try:
                with open(CONSOLE_LOG, "r", errors="replace") as f:
                    tail = f.read()[-1500:]
            except OSError:
                pass
            note = ""
            if not os.path.exists(self._rsp_path):
                note = ("\nxsim 未产生任何输出（rsp.txt 不存在）＝启动即失败；"
                        "下方 console 尾部是【上一次会话的残留】，与本次失败无关。")
            raise RuntimeError(
                f"xsim 进程已退出 rc={self.proc.returncode}"
                f"（rc 来自 bash→xsim.bat 包装链；127=命令未找到）{note}\n"
                f"stderr 尾部:\n{self._read_stderr_tail()}\nconsole 尾部:\n{tail}")

    # 上下文管理器
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.quit()
        return False
