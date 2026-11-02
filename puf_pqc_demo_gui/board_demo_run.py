# 上板全链路演示脚本: FW -> SEED(keygen) -> PUBK/PRIV -> SIGN -> VER
import serial, time, sys, random

PORT = "COM3"
ser = serial.Serial(PORT, 115200, bytesize=8, parity="N", stopbits=1, timeout=2)

def send(frame):
    print(f"[PC]   {frame if len(frame) <= 90 else frame[:80] + f'...<{len(frame)}B帧>'}")
    ser.write(frame.encode() + b"\r\n")

def recv(prefixes, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        raw = ser.readline()
        if not raw:
            continue
        line = raw.decode(errors="replace").strip()
        if not line:
            continue
        print(f"[FPGA] {line if len(line) <= 90 else line[:80] + f'...<{len(line)}B行>'}")
        for p in prefixes:
            if p in line:
                return line[line.find(p):]
    raise TimeoutError("timeout: " + "/".join(prefixes))

# 0. 同步
send("HELP"); time.sleep(0.2); ser.reset_input_buffer()
send("HELP")
recv(["cmds:"], timeout=15)
print("== 同步 OK ==\n")

# 1. 固件入库 FW (2KB, 00..FF 循环)
fw = bytes([i & 0xFF for i in range(2048)])
send("FW " + fw.hex())
line = recv(["RES FW SHA3 "], timeout=60)
sha = line.split()[-1]
print(f"== 固件入库 OK, SHA3-256 = {sha} ==\n")

# 2. SEED 直接注入种子 -> keygen (板上无真实 PUF 芯片, 走 direct 路径)
seed = bytes(random.getrandbits(8) for _ in range(32))
send("SEED " + seed.hex())
recv(["RES KEYGEN OK"], timeout=120)
print(f"== KEYGEN OK (seed={seed.hex()[:16]}...) ==\n")

# 3. 取公钥/私钥
send("PUBK")
pk = recv(["PUBK "], timeout=30).split("PUBK ", 1)[1]
print(f"== PUBK 收到 {len(pk)//2} 字节: {pk[:32]}... ==\n")
send("PRIV")
sk = recv(["PRIV "], timeout=30).split("PRIV ", 1)[1]
print(f"== PRIV 收到 {len(sk)//2} 字节: {sk[:32]}... ==\n")

# 4. 签名
send("SIGN")
line = recv(["SIG ", "RES NOT READY"], timeout=180)
sig = line.split("SIG ", 1)[1]
print(f"== SIGN OK, 签名 {len(sig)//2} 字节: {sig[:32]}... ==\n")

# 5. 验签
send("VER " + sig)
line = recv(["OK", "FAIL"], timeout=180)
print(f"== VERIFY 结果: {line} ==\n")

# 6. 篡改演示: 改签名1字节再验
bad = ("00" if sig[:2] != "00" else "01") + sig[2:]
send("VER " + bad)
line = recv(["OK", "FAIL"], timeout=180)
print(f"== 篡改签名1字节后 VERIFY: {line} (预期 FAIL) ==")

ser.close()
print("\n== 演示结束 ==")
