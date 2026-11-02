# 生成 keygen/sign 自测头文件 kat_kg_lv{2,3,5}.h
# seed -> keygen -> 期望输出流(rho|k|s1|s2|t1|t0|tr，32b 字，字内大端) + m/mlen
import re

LV  = [2, 3, 5]
S1  = {2: 48, 3: 80, 5: 84}     # 64b 字
S2  = {2: 48, 3: 96, 5: 96}
T0  = {2: 208, 3: 312, 5: 416}
T1  = {2: 160, 3: 240, 5: 320}
KGN = {lv: 8 + S1[lv] + S2[lv] + T1[lv] + T0[lv] + 4 for lv in LV}  # keygen 输出 64b 字数

def words(hexstr):
    b = bytes.fromhex(re.sub(r'\s+', '', hexstr))
    b += b'\x00' * (-len(b) % 4)
    return [int.from_bytes(b[i:i+4], 'big') for i in range(0, len(b), 4)]

def carr(name, rows):
    out = [f"static const uint32_t {name}[5][{len(rows[0])}] = {{"]
    out += ["  {" + ",".join(f"0x{w:08x}" for w in r) + "}," for r in rows]
    out.append("};")
    return out

for lv in LV:
    rd = lambda f: [l for l in open(f"KAT/{f}") if l.strip()][:5]
    mlen = [int(x, 16) for x in rd(f"mlen_{lv}.txt")]
    seed = [words(l) for l in rd(f"z_{lv}.txt")]           # keygen 的种子在 z_*.txt
    rho  = [words(l) for l in rd(f"rho_{lv}.txt")]
    k    = [words(l) for l in rd(f"k_{lv}.txt")]
    s1   = [words(l) for l in rd(f"s1_{lv}.txt")]
    s2   = [words(l) for l in rd(f"s2_{lv}.txt")]
    t1   = [words(l) for l in rd(f"t1_{lv}.txt")]
    t0   = [words(l) for l in rd(f"t0_{lv}.txt")]
    tr   = [words(l) for l in rd(f"tr_{lv}.txt")]
    mmax = max(2 * ((n + 7) // 8) for n in mlen)
    m    = [words(l) + [0] * (mmax - len(words(l))) for l in rd(f"m_{lv}.txt")]

    kgexp = []
    for i in range(5):
        w = rho[i] + k[i] + s1[i] + s2[i] + t1[i] + t0[i] + tr[i]
        assert len(w) == 2 * KGN[lv], f"lv{lv} tv{i}: {len(w)} != {2*KGN[lv]}"
        kgexp.append(w)

    hdr = ["#include <stdint.h>", f"/* Dilithium keygen/sign KAT, security level {lv} */"]
    hdr += carr(f"kat_seed_lv{lv}", seed)
    hdr += carr(f"kat_kgexp_lv{lv}", kgexp)
    hdr += carr(f"kat_mg_lv{lv}", m)
    hdr.append(f"static const uint32_t kat_mglen_lv{lv}[5] = {{{','.join(map(str, mlen))}}};")
    open(f"kat_kg_lv{lv}.h", "w").write("\n".join(hdr))
    print(f"level {lv}: kgexp {2*KGN[lv]} words/vec, m pad {mmax} words")

print("kat_kg_lv2/3/5.h 已生成")
