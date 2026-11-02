# 真板一键自检脚本：等 openocd(3333) → gdb 批量下固件 → COM3 串口自检(HELP×2 + CHAL 真 PUF)
# 由 一键启动_真板演示.bat 调用；也可单独跑: python board_bringup.py
import subprocess
import sys
import time
import socket

GDB = r"D:\FPGA\NucleiStudio\NucleiStudio\toolchain\gcc\bin\riscv-nuclei-elf-gdb.exe"
ELF = r"D:\FPGA\Dilithium-master\test_board_puf.elf"
PORT = sys.argv[1] if len(sys.argv) > 1 else "COM3"
CHAL_TEST = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"


def fail(msg):
    print(f"\n[FAIL] {msg}")
    sys.exit(1)


def wait_port(port, timeout=25):
    print(f"[1/3] 等待 openocd 监听 {port} ...")
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = socket.socket()
        s.settimeout(1)
        try:
            s.connect(("127.0.0.1", port))
            s.close()
            print("      openocd 就绪")
            return
        except OSError:
            time.sleep(0.5)
        finally:
            s.close()
    fail("openocd 25 秒内未就绪。检查：板子是否上电？调试器 USB 是否插好？")


def load_firmware():
    print("[2/3] gdb 下载固件 test_board_puf.elf ...")
    r = subprocess.run(
        [GDB, ELF, "--batch",
         "-ex", "target remote localhost:3333",
         "-ex", "monitor reset halt",
         "-ex", "load",
         "-ex", "set $pc=0x80000000",
         "-ex", "monitor resume",
         "-ex", "disconnect",
         "-ex", "quit"],
        capture_output=True, text=True, cwd=r"D:\FPGA\Dilithium-master")
    out = (r.stdout or "") + (r.stderr or "")
    if "Transfer rate" not in out:
        print(out)
        fail("固件下载失败（没看到 Transfer rate）。检查 openocd 窗口的报错。")
    print("      固件已下载并运行")


def smoke():
    import serial
    print(f"[3/3] 串口自检（{PORT} 115200 8N1）...")
    try:
        ser = serial.Serial(PORT, 115200, timeout=0.3)
    except Exception as e:
        fail(f"打不开 {PORT}：{e}。关闭占用串口的程序后重试。")

    def send(cmd):
        ser.write(cmd.encode() + b"\r\n")

    def wait_line(prefixes, timeout):
        t0 = time.time()
        while time.time() - t0 < timeout:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode(errors="replace").strip()
            if line:
                print("      < " + (line if len(line) <= 90 else line[:87] + "..."))
                for p in prefixes:
                    if p in line:
                        return line
        return None

    # 两次 HELP 同步（第一次吸收幻影字节）
    send("HELP")
    time.sleep(0.3)
    ser.reset_input_buffer()
    send("HELP")
    if not wait_line(["cmds:"], 5):
        ser.close()
        fail("HELP 无响应。固件可能没跑起来，重跑本脚本；仍不行则整板断电重来。")

    # CHAL 真 PUF 自检（固件内置 3 次重试）
    send("CHAL " + CHAL_TEST)
    line = wait_line(["RES KEYGEN OK", "RES PUF TIMEOUT"], 30)
    ser.close()
    if not line or "KEYGEN OK" not in line:
        fail("CHAL 未成功。检查 PUF 小板接线（3V3/GND/SCL/SDA）；断电重上电后重试。")
    print("      真 PUF 挑战-响应 + keygen 通过")


def main():
    wait_port(3333)
    load_firmware()
    smoke()
    print("\n===== 全部就绪：openocd 常驻 + 固件运行中 + PUF 链路正常 =====")
    print("现在可以在 GUI 里选 真实开发板(COM3) 连接并一键演示。")


if __name__ == "__main__":
    main()
