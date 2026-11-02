# 换种子对比公私钥: A -> B -> A(再来一次)
import serial, time, hashlib

ser = serial.Serial("COM3", 115200, bytesize=8, parity="N", stopbits=1, timeout=2)

def send(frame):
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
        for p in prefixes:
            if p in line:
                return line[line.find(p):]
    raise TimeoutError("timeout: " + "/".join(prefixes))

send("HELP"); time.sleep(0.2); ser.reset_input_buffer()
send("HELP"); recv(["cmds:"], timeout=15)
print("同步 OK\n")

SEED_A = bytes(range(32))                 # 000102...1f
SEED_B = bytes([0xFF - i for i in range(32)])  # fffefd...e0

results = []
for label, seed in [("种子A", SEED_A), ("种子B", SEED_B), ("种子A 第二次", SEED_A)]:
    send("SEED " + seed.hex())
    recv(["RES KEYGEN OK"], timeout=120)
    send("PUBK"); pk = recv(["PUBK "], timeout=30).split("PUBK ", 1)[1]
    send("PRIV"); sk = recv(["PRIV "], timeout=30).split("PRIV ", 1)[1]
    results.append((label, pk, sk))
    print(f"[{label}] seed = {seed.hex()}")
    print(f"  PUBK 前16字节 = {pk[:32]}")
    print(f"  PUBK 完整指纹 = {hashlib.sha256(pk.encode()).hexdigest()[:32]}...")
    print(f"  PRIV 前16字节 = {sk[:32]}")
    print(f"  PRIV 完整指纹 = {hashlib.sha256(sk.encode()).hexdigest()[:32]}...\n")

(_, pk_a, sk_a), (_, pk_b, sk_b), (_, pk_a2, sk_a2) = results
print("=" * 50)
print(f"种子A vs 种子B : 公钥{'相同' if pk_a == pk_b else '完全不同'} / 私钥{'相同' if sk_a == sk_b else '完全不同'}")
print(f"种子A vs A第二次: 公钥{'完全相同' if pk_a == pk_a2 else '不同!'} / 私钥{'完全相同' if sk_a == sk_a2 else '不同!'}")
ser.close()
