# 简易串口终端：打开 COM3 115200 8N1，输入一行回车即发送（自动加 \r\n）
# 用法: python serial_term.py [COM口]   退出: 输入 exit
import sys
import threading
import serial

port = sys.argv[1] if len(sys.argv) > 1 else "COM3"
ser = serial.Serial(port, 115200, timeout=0.1)
print(f"[已打开 {port} 115200 8N1，输入命令回车发送，exit 退出]")
print("[本地快捷命令: fw=发送2KB演示固件  ver=回传最近一次签名验签]")

last_sig = {"hex": None}


def reader():
    buf = b""
    while True:
        data = ser.read(4096)
        if data:
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                text = line.decode(errors="replace").rstrip()
                if text.startswith("SIG "):
                    last_sig["hex"] = text[4:].strip()
                    print(f"\n< SIG ({len(last_sig['hex'])} hex 已捕获, 输入 ver 回传验签)")
                else:
                    print("\n< " + text)


t = threading.Thread(target=reader, daemon=True)
t.start()

while True:
    try:
        cmd = input()
    except (EOFError, KeyboardInterrupt):
        break
    if cmd.strip().lower() == "exit":
        break
    if cmd.strip().lower() == "fw":
        # 本地快捷命令：发送 2KB 演示固件（0x00~0xFF 循环 8 遍）
        ser.write(b"FW " + bytes(range(256)).hex().encode() * 8 + b"\r\n")
        print("> [已发送 FW 2KB 演示固件]")
        continue
    if cmd.strip().lower() == "ver":
        if not last_sig["hex"]:
            print("! [还没有捕获到签名，先发 SIGN]")
        else:
            ser.write(b"VER " + last_sig["hex"].encode() + b"\r\n")
            print("> [已回传签名验签]")
        continue
    ser.write(cmd.encode() + b"\r\n")

ser.close()
