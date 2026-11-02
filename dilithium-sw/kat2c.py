import re

LV = [2, 3, 5]
Z64  = {2: 288, 3: 400, 5: 560}
T164 = {2: 160, 3: 240, 5: 320}
H64  = {2: 11,  3: 8,   5: 11}
FIX  = 2700
MMAX = 826   # 2*ceil(3300/8)，m 段统一补到这个长度

def words(hexstr, npad):
    b = bytes.fromhex(re.sub(r'\s+', '', hexstr))
    b += b'\x00' * (-len(b) % 4)
    w = [int.from_bytes(b[i:i+4], 'big') for i in range(0, len(b), 4)]
    return (w + [0] * npad)[:npad]

def carr(name, rows):
    out = [f"static const uint32_t {name}[5][{len(rows[0])}] = {{"]
    out += ["  {" + ",".join(f"0x{w:08x}" for w in r) + "}," for r in rows]
    out.append("};")
    return out

for lv in LV:
    rd = lambda f: [l for l in open(f"KAT/{f}") if l.strip()][:5]
    mlen = [int(x, 16) for x in rd(f"mlen_{lv}.txt")]
    rho  = [words(l, 8)            for l in rd(f"rho_{lv}.txt")]
    c    = [words(l, 8)            for l in rd(f"c_{lv}.txt")]
    z    = [words(l, 2*Z64[lv])    for l in rd(f"zs_{lv}.txt")]
    t1   = [words(l, 2*T164[lv])   for l in rd(f"t1_{lv}.txt")]
    h    = [words(l, 2*H64[lv])    for l in rd(f"h_{lv}.txt")]
    m    = [words(l, 2*((n+7)//8)) for l, n in zip(rd(f"m_{lv}.txt"), mlen)]
    m    = [r + [0]*(MMAX-len(r)) for r in m]

    stream = []
    for i in range(5):
        w = rho[i]+c[i]+z[i]+t1[i]+[0, mlen[i]]+m[i]+h[i]
        stream += w + [0]*(FIX-len(w))
    open(f"kat_stream_lv{lv}.hex", "w").write("\n".join(f"{w:08x}" for w in stream))
    open(f"kat_mlen_lv{lv}.hex",  "w").write("\n".join(f"{v:04x}" for v in mlen))

    hdr = ["#include <stdint.h>", f"/* Dilithium KAT, security level {lv} */"]
    hdr += carr(f"kat_rho_lv{lv}", rho) + carr(f"kat_c_lv{lv}", c)
    hdr += carr(f"kat_z_lv{lv}", z)   + carr(f"kat_t1_lv{lv}", t1)
    hdr += carr(f"kat_m_lv{lv}", m)   + carr(f"kat_h_lv{lv}", h)
    hdr.append(f"static const uint32_t kat_mlen_lv{lv}[5] = {{{','.join(map(str, mlen))}}};")
    open(f"kat_lv{lv}.h", "w").write("\n".join(hdr))
    print(f"level {lv} done")

print("hex x6 + kat_lv2/3/5.h 已生成")