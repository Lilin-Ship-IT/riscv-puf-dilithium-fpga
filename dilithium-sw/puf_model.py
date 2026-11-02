# PC 端 PUF 模拟器：扮演真 PUF 芯片，接第二个 USB-TTL（与 FPGA UART1 交叉连接）
# 协议与 sim tb 内行为模型一致：收 "CHAL <64hex>" → 回 3 次 "R <64hex>"
# R = SHAKE256(C || DEVICE_CONST)，与 sim_logs/EXPECTED.md 金样同源
# 用法: python puf_model.py [COM口] [DEV]   例: python puf_model.py COM5 0
import sys
import hashlib
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM5"
DEV = int(sys.argv[2]) if len(sys.argv) > 2 else 0
# 与 tb shake256_model.v 相同的设备常量（tb_top.v:756，换值=换芯片）
DEVICE_CONST = {
    0: bytes.fromhex("a5" * 32),
    1: bytes.fromhex("5a" * 32),
}


def puf_response(c: bytes) -> bytes:
    h = hashlib.shake_256()
    h.update(c + DEVICE_CONST[DEV])
    return h.digest(32)


def hex_ok(s: str, n: int) -> bool:
    if len(s) < n:
        return False
    try:
        int(s[:n], 16)
        return True
    except ValueError:
        return False


def main():
    ser = serial.Serial(PORT, 115200, timeout=0.1)
    print(f"[PUF 模拟器就位] 端口={PORT} 115200 8N1  DEV={DEV}，等待 CHAL ...（Ctrl+C 退出）")
    buf = b""
    while True:
        data = ser.read(1024)
        if data:
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                text = line.decode(errors="replace").strip()
                # strstr 容错：行内定位 "CHAL "
                i = text.find("CHAL ")
                if i >= 0 and hex_ok(text[i + 5:], 64):
                    c = bytes.fromhex(text[i + 5:i + 69])
                    r = puf_response(c)
                    print(f"[PUF] recv C={c.hex()}")
                    print(f"[PUF] R=SHAKE256(C||DEV{DEV})={r.hex()}")
                    # 连发 3 次冗余（跨首帧异常/耳聋期，与 tb 模型一致）
                    for _ in range(3):
                        ser.write(b"R " + r.hex().encode() + b"\r\n")
                elif text:
                    print(f"[PUF] 忽略: {text!r}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
