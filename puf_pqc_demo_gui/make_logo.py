# -*- coding: utf-8 -*-
"""重新绘制 assets/logo.png：圆角青绿渐变底 + 白描盾牌 + 密钥（信任根寓意）。
纯 PIL 实现（4x 超采样抗锯齿），不需要 QApplication。"""
import os
from PIL import Image, ImageDraw

S = 2048          # 超采样画布
OUT = 256
R = int(S * 0.24) # 圆角半径

try:
    import numpy as np
    y, x = np.mgrid[0:S, 0:S].astype(np.float64)
    t = (x + y) / (2.0 * S)
    c0 = np.array([0x4b, 0xbf, 0xa9])   # #4bbfa9
    c1 = np.array([0x2a, 0x9d, 0x8f])   # #2a9d8f
    c2 = np.array([0x1c, 0x72, 0x68])   # #1c7268
    t2 = t[..., None]
    img = np.where(t2 < 0.55,
                   c0 + (c1 - c0) * (t2 / 0.55),
                   c1 + (c2 - c1) * ((t2 - 0.55) / 0.45))
    # 顶部柔和高光
    hl = np.clip(1.0 - y / (0.6 * S), 0, 1) * 46
    base = Image.fromarray(img.astype("uint8"), "RGB").convert("RGBA")
    alpha = Image.fromarray((hl).astype("uint8"), "L")
    white = Image.new("RGBA", (S, S), (255, 255, 255, 255))
    white.putalpha(alpha)
    base.alpha_composite(white)
except ImportError:
    base = Image.new("RGBA", (S, S), (0x2a, 0x9d, 0x8f, 255))

# 圆角蒙版
mask = Image.new("L", (S, S), 0)
md = ImageDraw.Draw(mask)
md.rounded_rectangle([0, 0, S - 1, S - 1], radius=R, fill=255)
base.putalpha(mask)

u = S / 24.0

def quad(p0, p1, p2, n=60):
    pts = []
    for i in range(n + 1):
        tt = i / n
        x = (1 - tt) ** 2 * p0[0] + 2 * (1 - tt) * tt * p1[0] + tt ** 2 * p2[0]
        yy = (1 - tt) ** 2 * p0[1] + 2 * (1 - tt) * tt * p1[1] + tt ** 2 * p2[1]
        pts.append((x * u, yy * u))
    return pts

shield_pts = ([(12 * u, 3.0 * u), (19.4 * u, 5.9 * u), (19.4 * u, 11 * u)]
              + quad((19.4, 11), (19.4, 17.4), (12, 21))
              + quad((12, 21), (4.6, 17.4), (4.6, 11))[1:]
              + [(4.6 * u, 5.9 * u)])

# 盾内淡白填充
fill_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
fd = ImageDraw.Draw(fill_layer)
fd.polygon(shield_pts, fill=(255, 255, 255, 30))
base.alpha_composite(fill_layer)

d = ImageDraw.Draw(base)
# 盾牌白描边
w_shield = int(S * 0.026)
d.line(shield_pts + [shield_pts[0]], fill=(255, 255, 255, 255),
       width=w_shield, joint="curve")

# 盾内密钥（白色）
w_key = int(S * 0.034)
r = 2.5 * u
cx, cy = 9.7 * u, 9.5 * u
d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255, 255), width=w_key)
d.line([(11.5 * u, 11.3 * u), (16.6 * u, 16.4 * u)], fill=(255, 255, 255, 255), width=w_key)
d.line([(14.3 * u, 14.1 * u), (16.1 * u, 12.3 * u)], fill=(255, 255, 255, 255), width=w_key)
d.line([(15.6 * u, 15.4 * u), (17.4 * u, 13.6 * u)], fill=(255, 255, 255, 255), width=w_key)

logo = base.resize((OUT, OUT), Image.LANCZOS)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")
logo.save(out)
print("saved", out)
