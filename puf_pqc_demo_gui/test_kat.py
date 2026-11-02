# -*- coding: utf-8 -*-
"""
test_kat.py — Dilithium2 Python 后端 KAT 自测 + 硬件实测对拍（硬判据，不过即失败）

KAT 来源：D:\\FPGA\\Dilithium-master\\KAT\\（官方 KAT 向量，只读）
  z_2.txt   种子 seed(32B)          rho_2/k_2/tr_2  各 32B
  s1_2/s2_2 各 384B                t1_2 1280B  t0_2 1664B
  m_2.txt   消息（按 mlen_2 截断）  c_2 32B  zs_2 2304B  h_2 84B
  pk = rho|t1 (1312B)   sk = rho|k|tr|s1|s2|t0 (2528B)   sig = c~|z|h (2420B)

对拍来源：D:\\FPGA\\sim_logs\\EXPECTED.md 与 sim_scenA_dev0.log / run_scenD_dev1_cmd.log
  中提取的硬件实测值（完整值已存 expected_hw_values.json，提取方式见 README）。
"""
import sys, os, json, hashlib

if hasattr(sys.stdout, "reconfigure"):   # Windows GBK 控制台中文乱码修正
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "vendor"))
from dilithium_py.dilithium.default_parameters import Dilithium2  # noqa: E402

KAT_DIR = r"D:\FPGA\Dilithium-master\KAT"
N_KG, N_VER = 5, 15

out = []
def log(s=""):
    print(s)
    out.append(s)

def kat(name):
    with open(os.path.join(KAT_DIR, name)) as f:
        return [l.strip() for l in f if l.strip()]

def keygen_from_seed(seed32):
    """以给定 32B 种子做确定性 keygen（替换熵源，等价官方 KAT 流程）"""
    d = Dilithium2
    d.random_bytes = lambda n, s=seed32: s[:n]
    return d.keygen()

fails = 0
def check(name, ok, detail=""):
    global fails
    log(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        fails += 1

log("=" * 72)
log("test_kat.py — Dilithium2 (vendor: GiacomoPope/dilithium-py, MIT) KAT 自测 + 对拍")
log("=" * 72)

# ---------- a) keygen(官方KAT种子) → pk/sk 逐字节 ----------
zl, rl, kl, trl = kat("z_2.txt"), kat("rho_2.txt"), kat("k_2.txt"), kat("tr_2.txt")
s1l, s2l, t1l, t0l = kat("s1_2.txt"), kat("s2_2.txt"), kat("t1_2.txt"), kat("t0_2.txt")
ng = 0
for i in range(N_KG):
    pk, sk = keygen_from_seed(bytes.fromhex(zl[i]))
    pk_exp = (rl[i] + t1l[i]).lower()
    sk_exp = (rl[i] + kl[i] + trl[i] + s1l[i] + s2l[i] + t0l[i]).lower()
    if pk.hex() == pk_exp and sk.hex() == sk_exp:
        ng += 1
    else:
        check(f"keygen KAT[{i}]", False, "pk 或 sk 与官方向量不一致")
check(f"a) keygen 官方KAT逐字节一致 ({ng}/{N_KG})", ng == N_KG)

# ---------- b) verify(官方KAT pk, m, sig) 全过 ----------
ml, mll = kat("m_2.txt"), kat("mlen_2.txt")
cl, zsl, hl = kat("c_2.txt"), kat("zs_2.txt"), kat("h_2.txt")
nv = 0
for i in range(N_VER):
    pk = bytes.fromhex((rl[i] + t1l[i]).lower())
    mlen = int(mll[i], 16)
    m = bytes.fromhex(ml[i].lower())[:mlen]
    sig = bytes.fromhex((cl[i] + zsl[i] + hl[i]).lower())
    try:
        if Dilithium2.verify(pk, m, sig):
            nv += 1
    except Exception as e:
        check(f"verify KAT[{i}]", False, repr(e))
check(f"b) verify 官方KAT全过 ({nv}/{N_VER})", nv == N_VER)

# ---------- c) 自签自验回路 ----------
pk, sk = keygen_from_seed(bytes.fromhex(zl[0]))
m = hashlib.sha3_256(bytes(range(256)) * 8).digest()
sig = Dilithium2.sign(sk, m)
ok_loop = Dilithium2.verify(pk, m, sig)
bad = bytearray(sig); bad[100] ^= 0xFF
ok_neg = not Dilithium2.verify(pk, m, bytes(bad))
check("c) 自签自验回路 verify(pk,m,sig)==True", ok_loop)
check("c') 篡改签名1字节后 verify==False（负样本）", ok_neg)

# ---------- 对拍验收（vs 硬件实测, D:\FPGA\sim_logs） ----------
log("-" * 72)
log("对拍验收：Python 仿真后端 vs FPGA 硬件实测值（sim_logs）")
exp = json.load(open(os.path.join(BASE, "expected_hw_values.json")))
C = bytes(range(32))
R0 = hashlib.shake_256(C + b"\xa5" * 32).digest(32)
R1 = hashlib.shake_256(C + b"\x5a" * 32).digest(32)
check("PUF DEV0 R == 硬件实测", R0.hex() == "7a472b8311da5759b39f9618c8731a252a310d318f6dc71ca71c448f4cd31b75", R0.hex())
check("PUF DEV1 R == 硬件实测", R1.hex() == "1cc50e310670924813f112c4bcced97851b9bf346717ff74581fb5bf4c14b98b", R1.hex())
fw = bytes(range(256)) * 8
d0 = hashlib.sha3_256(fw).hexdigest()
fwt = bytearray(fw); fwt[0] ^= 1
d1 = hashlib.sha3_256(bytes(fwt)).hexdigest()
check("固件SHA3(good) == 硬件实测", d0 == "498cd3cc87a77b907debb761a2e6f59ed9edeaefc74f2c9c5c5f3b62f64c4aa1", d0)
check("固件SHA3(tampered fw[0]^=1) == 硬件实测", d1 == "40e61a44dc7f5a785b71eb98fe716760f2b0e73e99c824489594e26ba4df02e5", d1)
pk0, sk0 = keygen_from_seed(R0)
pk1, _ = keygen_from_seed(R1)
check("keygen(R_DEV0) PUBK == 硬件实测（2624hex 逐字节）", pk0.hex() == exp["DEV0_PUBK"], "前缀 " + pk0.hex()[:16])
check("keygen(R_DEV0) PRIV == 硬件实测（5056hex 逐字节）", sk0.hex() == exp["DEV0_PRIV"], "前缀 " + sk0.hex()[:16])
check("keygen(R_DEV1) PUBK == 硬件实测（2624hex 逐字节）", pk1.hex() == exp["DEV1_PUBK"], "前缀 " + pk1.hex()[:16])

log("-" * 72)
log(f"总计：{'全部通过' if fails == 0 else f'{fails} 项失败（硬失败）'}")
with open(os.path.join(BASE, "test_kat_output.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
sys.exit(1 if fails else 0)
