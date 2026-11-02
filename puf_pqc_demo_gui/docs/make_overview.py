# -*- coding: utf-8 -*-
"""把新五页 GUI 截图合成为 00_overview_annotated.png。

输入图片由 make_screenshots.py 在真实 Windows 桌面平台抓取；本脚本只用
PyQt5 拼接和标注，不再给单个控件沿用旧单页编号。
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "docs", "screenshots")

from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QApplication

app = QApplication([])
if app.platformName().lower() != "windows":
    raise RuntimeError("总览图必须使用真实 Windows 桌面平台，禁止 offscreen")

cards = [
    ("01_home.png", "演示首页｜一键开始演示"),
    ("02_connect.png", "1 连接设备｜全链路仿真（RTL）/ 硬件开发板"),
    ("03_firmware.png", "2 固件下载｜SHA3-256 完整摘要 + 金样比对"),
    ("04_keys.png", "3 密钥生成｜CHAL / SEED + 256bit 激励计数"),
    ("04_sign_verify_pass.png", "4 签名与验证｜PASS / FAIL + 篡改演示"),
]

width, height = 1600, 1800
image = QImage(width, height, QImage.Format_ARGB32)
image.fill(QColor("#f4f7fb"))
painter = QPainter(image)
painter.setRenderHint(QPainter.Antialiasing)
painter.setRenderHint(QPainter.SmoothPixmapTransform)
painter.setPen(QColor("#0f172a"))
painter.setFont(QFont("Microsoft YaHei", 25, QFont.Bold))
painter.drawText(QRect(36, 22, width - 72, 52), Qt.AlignCenter,
                 "可信启动演示平台｜五页操作总览")

thumb_w, thumb_h = 752, 494
caption_h = 48
x_positions = [36, width - 36 - thumb_w]
y_positions = [94, 94 + caption_h + thumb_h + 24,
               94 + 2 * (caption_h + thumb_h + 24)]

for index, (filename, caption) in enumerate(cards):
    path = os.path.join(OUT, filename)
    pixmap = QPixmap(path)
    if pixmap.isNull():
        painter.end()
        raise RuntimeError("缺少或无法读取截图: %s；请先运行 make_screenshots.py" % path)
    row, col = divmod(index, 2)
    x = x_positions[col] if index < 4 else (width - thumb_w) // 2
    y = y_positions[row]
    painter.setPen(QColor("#334155"))
    painter.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
    painter.drawText(QRect(x, y, thumb_w, caption_h), Qt.AlignCenter, caption)
    frame = QRect(x, y + caption_h, thumb_w, thumb_h)
    painter.setPen(QPen(QColor("#cbd5e1"), 2))
    painter.setBrush(QColor("white"))
    painter.drawRoundedRect(frame, 8, 8)
    scaled = pixmap.scaled(thumb_w - 4, thumb_h - 4,
                           Qt.KeepAspectRatio, Qt.SmoothTransformation)
    target = QRect(x + (thumb_w - scaled.width()) // 2,
                   y + caption_h + (thumb_h - scaled.height()) // 2,
                   scaled.width(), scaled.height())
    painter.drawPixmap(target, scaled)

painter.end()
output = os.path.join(OUT, "00_overview_annotated.png")
if not image.save(output):
    raise RuntimeError("总览图保存失败: " + output)
print("saved 00_overview_annotated.png, 5 page cards")
