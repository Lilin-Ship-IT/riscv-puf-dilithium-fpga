# -*- coding: utf-8 -*-
"""PUF + Dilithium 可信启动演示平台（PyQt5）。"""
import sys
import os
import csv
import json
import random
import datetime
import time
import subprocess

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout, QVBoxLayout, QHBoxLayout,
    QGroupBox, QPushButton, QLineEdit, QComboBox, QPlainTextEdit, QLabel,
    QRadioButton, QFileDialog, QMessageBox, QStackedWidget, QListWidget,
    QListWidgetItem, QFrame, QProgressBar, QTabWidget, QSpinBox, QCheckBox,
    QScrollArea, QGraphicsDropShadowEffect, QSizePolicy, QSplitter,
    QButtonGroup,
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer, QSize
from PyQt5.QtGui import (
    QFont, QIcon, QPixmap, QPainter, QPen, QColor, QBrush, QPainterPath,
)

from backend import (
    SimBackend, SerialBackend, XsimBackend, DEFAULT_CHAL, builtin_firmware,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "可信启动演示平台"
MONO = QFont("Consolas", 10)
BIG = QFont("Consolas", 28, QFont.Bold)
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "baud": 115200,
    "timeout": 10,
    "tamper_random": True,
    "dark": False,
    "backend": "xsim",
}

PALETTES = {
    "light": {
        "accent": "#2a9d8f", "accent_bg": "#e2f2ee",
        "ok": "#2e8b6e", "ok_bg": "#e9f5ef", "ok_border": "#9fd6bf",
        "err": "#d64545", "err_bg": "#fceeee", "err_border": "#f0b3b3",
        "warn": "#c98a1e", "warn_bg": "#fdf3e0",
        "muted": "#6f857e", "muted_bg": "#edf3f1",
        "card": "#ffffff", "border": "#dde8e3", "text": "#1b2f2a",
    },
    "dark": {
        "accent": "#4fc0ae", "accent_bg": "#16302a",
        "ok": "#4ecb8d", "ok_bg": "#12291f", "ok_border": "#1f6b4a",
        "err": "#f0726f", "err_bg": "#2c1718", "err_border": "#8f3535",
        "warn": "#eba93f", "warn_bg": "#2a2110",
        "muted": "#84a59e", "muted_bg": "#1a2a26",
        "card": "#152420", "border": "#28423a", "text": "#e3efe9",
    },
}

QSS_LIGHT = """
QWidget { font-family: "SimSun"; font-size: 15px; font-weight: 600; color: #1b2f2a; }
QMainWindow, QWidget#root { background: #f4f7f6; }
QFrame#header { background: #ffffff; border-bottom: 1px solid #dde8e3; }
QFrame#sidebar { background: #ffffff; border-right: 1px solid #dde8e3; }
QLabel#appTitle { font-size: 24px; font-weight: 800; color: #14312a; }
QLabel#appSubtitle, QLabel#muted { color: #6f857e; font-size: 13px; font-weight: 400; }
QLabel#pageTitle { font-size: 30px; font-weight: 800; color: #14312a; margin-bottom: 6px; }
QLabel#sideTitle { color: #14312a; font-size: 17px; font-weight: 700; }
QLabel#navTitle { color: #1b2f2a; font-size: 16px; font-weight: 700; }
QLabel#navDesc { color: #87a098; font-size: 12px; font-weight: 400; }
QLabel#cardTitle { font-size: 17px; font-weight: 700; color: #2a4a41; }
QLabel#stepHint { font-size: 15px; font-weight: 700; color: #3d5a50; }
QListWidget#nav { background: transparent; border: none; outline: 0; }
QListWidget#nav::item { margin: 3px 12px; border-radius: 10px; }
QListWidget#nav::item:selected, QListWidget#nav::item:hover { background: transparent; }
QGroupBox { background: #ffffff; border: 1px solid #dde8e3; border-radius: 14px;
            padding: 14px 16px 14px 16px; font-weight: 700; font-size: 16px; }
QGroupBox[active="true"] { border: 2px solid #f3af44; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox { background: #ffffff; border: 1px solid #cfded7;
    border-radius: 8px; padding: 8px 10px; min-height: 22px;
    selection-background-color: #2a9d8f; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus { border: 2px solid #2a9d8f; }
QLineEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled, QSpinBox:disabled { background: #f0f4f2; color: #9cb0a8; }
QPushButton { background: #ffffff; border: 1px solid #cfded7; border-radius: 9px;
              padding: 10px 18px; min-height: 22px; font-weight: 600; }
QPushButton:hover { background: #edf5f2; border-color: #9cb8af; }
QPushButton:pressed { background: #e0efe9; }
QPushButton:disabled { background: #f4f7f6; color: #9cb0a8; border-color: #e3ece8; }
QPushButton#primary { background: #2a9d8f; border: none; color: #ffffff; font-weight: 700; }
QPushButton#primary:hover { background: #238577; }
QPushButton#primary:disabled { background: #b6d5cf; color: #eef5f2; }
QPushButton#hero { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #2a9d8f, stop:1 #45b8a4);
                   border: none; border-radius: 12px; color: #ffffff;
                   font-size: 18px; font-weight: 700; padding: 16px 28px; }
QPushButton#hero:hover { background: #238577; }
QPushButton#danger { color: #c23b3b; background: #fdf0f0; border-color: #f2c9c9; }
QPushButton#danger:hover { background: #fbe3e3; }
QFrame#segBar { background: #eaf2ef; border-radius: 11px; }
QPushButton#seg { background: transparent; border: none; border-radius: 9px;
                  padding: 10px 22px; font-weight: 700; color: #41605a; }
QPushButton#seg:checked { background: #2a9d8f; color: #ffffff; }
QPushButton#seg:disabled { color: #9cb0a8; }
QFrame#heroCard { background: #ffffff; border: 1px solid #dde8e3; border-radius: 14px; }
QLabel#kpiTitle { color: #6f857e; font-size: 13px; font-weight: 400; }
QLabel#kpiValue { color: #14312a; font-size: 26px; font-weight: 800; font-family: "Consolas"; }
QLabel#kpiSub { color: #9cb0a8; font-size: 12px; font-weight: 400; }
QFrame#logPanel { background: #ffffff; border: 1px solid #dde8e3; border-radius: 12px; }
QLabel#logTitle { font-weight: 700; color: #2a4a41; }
QProgressBar { border: none; border-radius: 3px; background: #dde8e3; max-height: 6px; }
QProgressBar::chunk { background: #2a9d8f; border-radius: 3px; }
QTabWidget::pane { border: 1px solid #dde8e3; border-radius: 9px; background: #ffffff; }
QTabBar::tab { background: #eff5f2; padding: 9px 20px; border: 1px solid #dae6e1; }
QTabBar::tab:selected { background: #2a9d8f; color: #ffffff; }
QCheckBox, QRadioButton { spacing: 8px; }
QSplitter#mainSplit::handle:vertical { height: 5px; background: #dde8e3; margin: 2px 60px; border-radius: 2px; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #cfded7; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #9cb8af; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #cfded7; border-radius: 5px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #9cb8af; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QToolTip { color: #ffffff; background: #14312a; border: none; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
"""

QSS_DARK = """
QWidget { font-family: "SimSun"; font-size: 15px; font-weight: 600; color: #e3efe9; }
QMainWindow, QWidget#root { background: #0c1614; }
QFrame#header { background: #122019; border-bottom: 1px solid #264139; }
QFrame#sidebar { background: #101c18; border-right: 1px solid #264139; }
QLabel#appTitle { font-size: 24px; font-weight: 800; color: #e8f4ee; }
QLabel#appSubtitle, QLabel#muted { color: #84a59e; font-size: 13px; font-weight: 400; }
QLabel#pageTitle { font-size: 30px; font-weight: 800; color: #e8f4ee; margin-bottom: 6px; }
QLabel#sideTitle { color: #e8f4ee; font-size: 17px; font-weight: 700; }
QLabel#navTitle { color: #e3efe9; font-size: 16px; font-weight: 700; }
QLabel#navDesc { color: #5f7a72; font-size: 12px; font-weight: 400; }
QLabel#cardTitle { font-size: 17px; font-weight: 700; color: #b9d4ca; }
QLabel#stepHint { font-size: 15px; font-weight: 700; color: #a9c8bd; }
QListWidget#nav { background: transparent; border: none; outline: 0; }
QListWidget#nav::item { margin: 3px 12px; border-radius: 10px; }
QListWidget#nav::item:selected, QListWidget#nav::item:hover { background: transparent; }
QGroupBox { background: #152420; border: 1px solid #28423a; border-radius: 14px;
            padding: 14px 16px 14px 16px; font-weight: 700; font-size: 16px; }
QGroupBox[active="true"] { border: 2px solid #eba93f; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox { background: #101c18; border: 1px solid #2e4a40;
    border-radius: 8px; padding: 8px 10px; min-height: 22px; color: #e3efe9;
    selection-background-color: #2a9d8f; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus { border: 2px solid #4fc0ae; }
QLineEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled, QSpinBox:disabled { background: #132119; color: #5b7069; }
QPushButton { background: #1a2c26; border: 1px solid #2e4a40; border-radius: 9px;
              padding: 10px 18px; min-height: 22px; font-weight: 600; color: #e3efe9; }
QPushButton:hover { background: #213a32; border-color: #4fc0ae; }
QPushButton:pressed { background: #1b302a; }
QPushButton:disabled { background: #15241e; color: #5b7069; border-color: #264139; }
QPushButton#primary { background: #2a9d8f; border: none; color: #ffffff; font-weight: 700; }
QPushButton#primary:hover { background: #238577; }
QPushButton#primary:disabled { background: #1f352e; color: #5b7069; }
QPushButton#hero { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #2a9d8f, stop:1 #45b8a4);
                   border: none; border-radius: 12px; color: #ffffff;
                   font-size: 18px; font-weight: 700; padding: 16px 28px; }
QPushButton#hero:hover { background: #238577; }
QPushButton#danger { color: #f0726f; background: #2c1718; border-color: #7f2a2a; }
QPushButton#danger:hover { background: #3a1d1f; }
QFrame#segBar { background: #182a24; border-radius: 11px; }
QPushButton#seg { background: transparent; border: none; border-radius: 9px;
                  padding: 10px 22px; font-weight: 700; color: #a9c8bd; }
QPushButton#seg:checked { background: #2a9d8f; color: #ffffff; }
QPushButton#seg:disabled { color: #5b7069; }
QFrame#heroCard { background: #152420; border: 1px solid #28423a; border-radius: 14px; }
QLabel#kpiTitle { color: #84a59e; font-size: 13px; font-weight: 400; }
QLabel#kpiValue { color: #e8f4ee; font-size: 26px; font-weight: 800; font-family: "Consolas"; }
QLabel#kpiSub { color: #5f7a72; font-size: 12px; font-weight: 400; }
QFrame#logPanel { background: #152420; border: 1px solid #28423a; border-radius: 12px; }
QLabel#logTitle { font-weight: 700; color: #b9d4ca; }
QProgressBar { border: none; border-radius: 3px; background: #1a2c26; max-height: 6px; }
QProgressBar::chunk { background: #45b8a4; border-radius: 3px; }
QTabWidget::pane { border: 1px solid #28423a; border-radius: 9px; background: #152420; }
QTabBar::tab { background: #1a2c26; padding: 9px 20px; border: 1px solid #2e4a40; color: #a9c8bd; }
QTabBar::tab:selected { background: #2a9d8f; color: #ffffff; }
QCheckBox, QRadioButton { spacing: 8px; }
QSplitter#mainSplit::handle:vertical { height: 5px; background: #28423a; margin: 2px 60px; border-radius: 2px; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #2e4a40; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #4fc0ae; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #2e4a40; border-radius: 5px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #4fc0ae; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QToolTip { color: #ffffff; background: #0f1a16; border: none; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
"""

QSS = QSS_LIGHT  # 兼容旧脚本（docs/make_screenshots.py 引用 main.QSS）


def ts():
    return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]


def load_settings():
    cfg = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_settings(cfg):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def make_icon(name, color, size=22):
    """QPainter 自绘线性图标（2x 超采样，无外部资源文件）。"""
    import math
    big = size * 2
    pix = QPixmap(big, big)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    c = QColor(color)
    p.setPen(QPen(c, big * 0.075, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    u = big / 24.0

    def line(x1, y1, x2, y2):
        p.drawLine(int(x1 * u), int(y1 * u), int(x2 * u), int(y2 * u))

    def rect(x, y, w, h, r=0):
        p.drawRoundedRect(int(x * u), int(y * u), int(w * u), int(h * u), r * u, r * u)

    def circle(cx, cy, r):
        p.drawEllipse(int((cx - r) * u), int((cy - r) * u), int(2 * r * u), int(2 * r * u))

    def dot(cx, cy, r):
        p.save()
        p.setBrush(QBrush(c))
        p.setPen(Qt.NoPen)
        p.drawEllipse(int((cx - r) * u), int((cy - r) * u), int(2 * r * u), int(2 * r * u))
        p.restore()

    def poly(pts, close=False, fill=False):
        path = QPainterPath()
        path.moveTo(pts[0][0] * u, pts[0][1] * u)
        for x, y in pts[1:]:
            path.lineTo(x * u, y * u)
        if close:
            path.closeSubpath()
        if fill:
            p.save()
            p.setBrush(QBrush(c))
            p.setPen(Qt.NoPen)
            p.drawPath(path)
            p.restore()
        else:
            p.drawPath(path)

    def bar(x, y, w, h):
        p.save()
        p.setBrush(QBrush(c))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(int(x * u), int(y * u), int(w * u), int(h * u), u, u)
        p.restore()

    if name == "home":
        poly([(3, 12), (12, 4), (21, 12)])
        poly([(6, 10), (6, 20), (18, 20), (18, 10)])
    elif name == "link":
        circle(7.5, 7.5, 4.2)
        circle(16.5, 16.5, 4.2)
        line(10.5, 10.5, 13.5, 13.5)
    elif name == "chip":
        rect(6, 6, 12, 12, 1.5)
        rect(10, 10, 4, 4)
        for x in (8, 12, 16):
            line(x, 3, x, 6)
            line(x, 18, x, 21)
        for y in (8, 12, 16):
            line(3, y, 6, y)
            line(18, y, 21, y)
    elif name == "pen":
        line(6, 18, 17, 7)
        line(17, 7, 19, 5)
        line(4, 21, 20, 21)
    elif name == "doc":
        rect(6, 3, 12, 18, 1.5)
        line(9, 8, 15, 8)
        line(9, 12, 15, 12)
        line(9, 16, 13, 16)
    elif name == "chart":
        bar(5, 12, 4, 8)
        bar(11, 8, 4, 12)
        bar(17, 5, 4, 15)
    elif name == "gear":
        circle(12, 12, 3.5)
        for k in range(8):
            a = math.pi / 4 * k
            line(12 + 5.5 * math.cos(a), 12 + 5.5 * math.sin(a),
                 12 + 8 * math.cos(a), 12 + 8 * math.sin(a))
    elif name == "info":
        circle(12, 12, 8.5)
        dot(12, 8, 1.1)
        line(12, 11.5, 12, 16.5)
    elif name == "shield":
        path = QPainterPath()
        path.moveTo(12 * u, 3 * u)
        path.lineTo(19.5 * u, 6 * u)
        path.lineTo(19.5 * u, 11 * u)
        path.quadTo(19.5 * u, 17.5 * u, 12 * u, 21 * u)
        path.quadTo(4.5 * u, 17.5 * u, 4.5 * u, 11 * u)
        path.lineTo(4.5 * u, 6 * u)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "shieldcheck":
        path = QPainterPath()
        path.moveTo(12 * u, 3 * u)
        path.lineTo(19.5 * u, 6 * u)
        path.lineTo(19.5 * u, 11 * u)
        path.quadTo(19.5 * u, 17.5 * u, 12 * u, 21 * u)
        path.quadTo(4.5 * u, 17.5 * u, 4.5 * u, 11 * u)
        path.lineTo(4.5 * u, 6 * u)
        path.closeSubpath()
        p.drawPath(path)
        poly([(8.5, 12), (11, 14.8), (15.8, 8.8)])
    elif name == "check":
        poly([(5, 12.5), (10, 17.5), (19, 6.5)])
    elif name == "alert":
        poly([(12, 4), (21, 19), (3, 19)], close=True)
        line(12, 9.5, 12, 14)
        dot(12, 16.5, 1.0)
    elif name == "key":
        circle(8, 8, 4)
        line(11, 11, 19, 19)
        line(15, 15, 17.5, 12.5)
    elif name == "play":
        poly([(8, 5), (19, 12), (8, 19)], close=True, fill=True)
    elif name == "dice":
        rect(4, 4, 16, 16, 3)
        dot(9, 9, 1.3)
        dot(15, 15, 1.3)
    elif name == "save":
        poly([(5, 13), (5, 19), (19, 19), (19, 13)])
        line(12, 4, 12, 14)
        poly([(8.5, 10.5), (12, 14), (15.5, 10.5)])
    p.end()
    return pix


class BitGrid(QWidget):
    """256bit 点阵（16×16）：固件摘要可视化。PASS 绿 / FAIL 红 / 篡改字节描边高亮。"""

    def __init__(self, pal):
        super().__init__()
        self._pal = pal
        self._data = None
        self._state = "idle"
        self._hl_byte = -1
        self._cell = 11
        side = 16 * self._cell + 2
        self.setFixedSize(side, side)

    def set_bits(self, data, state, hl_byte=-1):
        self._data = data
        self._state = state
        self._hl_byte = hl_byte
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self._pal()
        on, off = {
            "idle": (pal["muted"], pal["muted_bg"]),
            "done": (pal["ok"], pal["ok_border"]),
            "fail": (pal["err"], pal["err_border"]),
        }[self._state]
        if self._state == "idle":
            on = pal["muted_bg"]
        for i in range(256):
            row, col = divmod(i, 16)
            x = 1 + col * self._cell
            y = 1 + row * self._cell
            bit = 0
            if self._data is not None:
                bit = (self._data[i >> 3] >> (7 - (i & 7))) & 1
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(on if bit else off)))
            p.drawRoundedRect(x, y, self._cell - 2, self._cell - 2, 2, 2)
        if 0 <= self._hl_byte < 32 and self._data is not None:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(pal["text"]), 2))
            for k in range(8):
                row, col = divmod(self._hl_byte * 8 + k, 16)
                p.drawRect(col * self._cell, row * self._cell, self._cell, self._cell)
        p.end()


class Worker(QThread):
    log = pyqtSignal(str, str)
    step = pyqtSignal(str)
    result = pyqtSignal(str, object)
    failed = pyqtSignal(str)
    finished_ok = pyqtSignal(object)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.finished_ok.emit(self.fn(self))
        except Exception as e:
            import traceback
            with open(os.path.join(BASE_DIR, "gui_error.log"), "a", encoding="utf-8") as f:
                f.write(f"\n[{ts()}]\n{traceback.format_exc()}")
            self.failed.emit(str(e))


class ChainWidget(QWidget):
    """信任链流水线：固件度量 → PUF 响应 → 密钥生成 → 签名 → 验签。

    每格四种状态：idle（等待）/ running（执行中）/ done（✓ 完成）/ fail（✗ 失败）。
    """

    STAGES = ("固件度量", "PUF 响应", "密钥生成", "签名", "验签")

    def __init__(self, pal):
        super().__init__()
        self._pal = pal
        self.states = ["idle"] * len(self.STAGES)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        self.frames = []
        self.name_lbls = []
        self.state_lbls = []
        self.arrows = []
        for i, name in enumerate(self.STAGES):
            f = QFrame()
            f.setMinimumHeight(66)
            v = QVBoxLayout(f)
            v.setContentsMargins(10, 8, 10, 8)
            v.setSpacing(3)
            n = QLabel(f"{i + 1}  {name}")
            n.setMinimumHeight(20)
            s = QLabel("等待")
            s.setMinimumHeight(18)
            v.addWidget(n)
            v.addWidget(s)
            self.frames.append(f)
            self.name_lbls.append(n)
            self.state_lbls.append(s)
            h.addWidget(f, 1)
            if i < len(self.STAGES) - 1:
                a = QLabel("→")
                a.setAlignment(Qt.AlignCenter)
                self.arrows.append(a)
                h.addWidget(a)
        self._refresh()

    def _refresh(self):
        pal = self._pal()
        style_map = {
            "idle": (pal["card"], pal["border"], pal["muted"], pal["muted"], "等待"),
            "running": (pal["accent_bg"], pal["accent"], pal["accent"], pal["accent"], "执行中 …"),
            "done": (pal["ok_bg"], pal["ok_border"], pal["ok"], pal["ok"], "✓ 完成"),
            "fail": (pal["err_bg"], pal["err_border"], pal["err"], pal["err"], "✗ 失败"),
        }
        for i, state in enumerate(self.states):
            bg, border, name_c, state_c, text = style_map[state]
            weight = "700" if state == "running" else "600"
            self.frames[i].setStyleSheet(
                f"QFrame {{ background:{bg}; border:2px solid {border}; border-radius:9px; }}")
            self.name_lbls[i].setStyleSheet(
                f"color:{name_c}; font-weight:{weight}; font-size:13px; border:none;")
            self.state_lbls[i].setStyleSheet(
                f"color:{state_c}; font-size:12px; border:none;")
            self.state_lbls[i].setText(text)
        for a in self.arrows:
            a.setStyleSheet(f"color:{pal['muted']}; font-size:16px; font-weight:700;")

    def reset(self):
        self.states = ["idle"] * len(self.STAGES)
        self._refresh()

    def set_running(self, i):
        for j in range(len(self.STAGES)):
            if j < i:
                if self.states[j] != "fail":
                    self.states[j] = "done"
            elif j == i:
                self.states[j] = "running"
            else:
                self.states[j] = "idle"
        self._refresh()

    def set_state(self, i, state):
        self.states[i] = state
        self._refresh()


class DeviceLogView(QFrame):
    """页底"设备实况"：RTL 模式滚动显示 xsim console 尾部；真板模式回显串口帧。
    让用户随时看到底层真实运行到哪一步。"""

    def __init__(self):
        super().__init__()
        self.setObjectName("logPanel")
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 6, 12, 8)
        v.setSpacing(4)
        self.cap = QLabel("设备实况（未连接）")
        self.cap.setObjectName("logTitle")
        v.addWidget(self.cap)
        self.edit = QPlainTextEdit()
        self.edit.setReadOnly(True)
        self.edit.setFont(MONO)
        self.edit.setMaximumBlockCount(400)
        self.edit.setFixedHeight(110)
        v.addWidget(self.edit)

    def append_lines(self, lines):
        if not lines:
            return
        self.edit.appendPlainText("\n".join(lines))
        sb = self.edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_caption(self, text):
        self.cap.setText(text)


class MainWindow(QMainWindow):
    PAGE_HINTS = (
        "从这里一键演示，或按左侧步骤逐项操作",
        "第 1 步：建立连接（全链路仿真 / 硬件开发板）",
        "第 2 步：固件下载与 SHA3-256 度量",
        "第 3 步：PUF 挑战与密钥生成",
        "第 4 步：签名、验签与防篡改演示",
    )

    def __init__(self, fast=False, force_sim=False):
        super().__init__()
        self.fast = fast
        self.force_sim = force_sim   # 截图/自测专用：_connect 强制走 SimBackend
        self.backend = None
        self.worker = None
        self.fw_bytes = builtin_firmware()
        self.sig_wire = None
        self._is_busy = False
        self._connecting = False
        self._demo_after_connect = False
        self._action_buttons = []
        self.chains = []

        self.settings = load_settings()
        self.dark = bool(self.settings.get("dark", False))

        # 会话状态（供状态栏 / 首页徽标使用）
        self.fw_digest = None          # 固件 SHA3-256 hex
        self.pk_bytes = None
        self.verify_count = 0
        self.pass_count = 0
        self.verify_times = []         # 历次验签耗时 ms
        self.report = []               # 报告事件 {time, mode, op, detail, result}
        self._last_tamper = None       # ("签名"|"固件", 字节序号)
        self._aborted = False          # 用户点了「终止当前操作」
        self._openocd_proc = None      # GUI 托管的 openocd（拉板时启动）
        self._console_off = 0          # sim_link_console.log 已读偏移
        self.devlog_views = []         # 各页底部"设备实况"视图
        self._t0 = time.time()

        self.setWindowTitle(APP_NAME)
        self.resize(1440, 920)
        self.setMinimumSize(1240, 800)
        logo = os.path.join(BASE_DIR, "assets", "logo.png")
        if os.path.exists(logo):
            self.setWindowIcon(QIcon(logo))

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(0)
        outer.addLayout(body, 1)
        self.sidebar = self._build_sidebar()
        body.addWidget(self.sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 18, 24, 12)
        content_layout.setSpacing(10)
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 1)
        body.addWidget(content, 1)

        self.stack.addWidget(self._scroll(self._build_home_page()))       # 0
        self.stack.addWidget(self._scroll(self._build_connect_page()))    # 1
        self.stack.addWidget(self._scroll(self._build_fw_page()))         # 2
        self.stack.addWidget(self._scroll(self._build_key_page()))        # 3
        self.stack.addWidget(self._scroll(self._build_sign_page()))       # 4
        # 通信日志放进竖向分割条：可拖拽调高矮，也可用按钮整个收起
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setObjectName("mainSplit")
        self.splitter.addWidget(self.stack)
        self.splitter.addWidget(self._build_log_panel())
        self.splitter.setCollapsible(0, False)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([640, 150])
        content_layout.addWidget(self.splitter, 1)
        content_layout.addLayout(self._build_page_footer())

        self.gb = {
            "measure": self.gb_fw, "puf": self.gb_puf, "keygen": self.gb_keys,
            "sign": self.gb_alg, "verify": self.gb_alg,
        }
        self.nav.currentRowChanged.connect(self._go_page)
        self._refresh_ports()
        self._backend_kind_changed()
        self._set_conn_state("disconnected")
        self._set_verdict(None)
        self.nav.setCurrentRow(0)
        self._apply_theme()
        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._tick_uptime)
        self._stats_timer.start(1000)
        # 设备实况刷新：RTL 模式 tail xsim console
        self._devlog_timer = QTimer(self)
        self._devlog_timer.timeout.connect(self._poll_device_log)
        self._devlog_timer.start(1000)
        # 步骤进度条刷新（RTL 长操作估算进度）
        self._prog_timer = QTimer(self)
        self._prog_timer.timeout.connect(self._tick_step_progress)
        self._prog_timer.start(500)
        self._log("SYS", "系统就绪。请选择运行方式并连接设备（全链路仿真或硬件开发板）。")

    def _tick_uptime(self):
        secs = int(time.time() - self._t0)
        self.stat_uptime.setText(f"运行时长  {secs // 60:02d}:{secs % 60:02d}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 侧栏约为窗口宽度的 1/6，窗口拉大时同步加宽
        if hasattr(self, "sidebar"):
            w = max(280, min(430, self.width() // 6))
            if self.sidebar.width() != w:
                self.sidebar.setFixedWidth(w)

    # ------------------------------------------------------------------ 主题
    def _pal(self):
        return PALETTES["dark" if self.dark else "light"]

    def _apply_theme(self):
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(QSS_DARK if self.dark else QSS_LIGHT)
        self.btn_theme.setText("☀ 浅色" if self.dark else "☾ 深色")
        self._restyle_dynamic()

    def _restyle_dynamic(self):
        """主题切换后重刷所有内联样式的动态控件。"""
        for chain in self.chains:
            chain._refresh()
        self._refresh_chips()
        self._refresh_badges()
        self._refresh_nav()
        cur = getattr(self, "_verdict_state", None)
        if cur:
            self._set_verdict(cur[0], cur[1], cur[2])
        else:
            self._set_verdict(None)

    def _toggle_theme(self):
        self.dark = not self.dark
        self.settings["dark"] = self.dark
        save_settings(self.settings)
        self.chk_dark.blockSignals(True)
        self.chk_dark.setChecked(self.dark)
        self.chk_dark.blockSignals(False)
        self._apply_theme()

    # ------------------------------------------------------------------ 骨架
    def _chip(self, text="—"):
        lbl = QLabel(text)
        lbl.setStyleSheet(self._chip_style())
        return lbl

    def _chip_style(self):
        pal = self._pal()
        return (f"QLabel {{ color:{pal['muted']}; background:{pal['muted_bg']}; "
                "border-radius:10px; padding:5px 12px; font-size:13px; }")

    def _shadow(self, widget, blur=22, dy=4):
        effect = QGraphicsDropShadowEffect(widget)
        effect.setBlurRadius(blur)
        effect.setOffset(0, dy)
        effect.setColor(QColor(0, 0, 0, 80) if self.dark else QColor(20, 50, 38, 26))
        widget.setGraphicsEffect(effect)

    def _build_header(self):
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(80)
        h = QHBoxLayout(header)
        h.setContentsMargins(24, 12, 24, 12)
        logo_path = os.path.join(BASE_DIR, "assets", "logo.png")
        logo = QLabel()
        logo.setFixedSize(48, 48)
        if os.path.exists(logo_path):
            logo.setPixmap(QPixmap(logo_path).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo.setText("PD")
            logo.setAlignment(Qt.AlignCenter)
            logo.setStyleSheet("background:#2a9d8f;color:white;border-radius:10px;font-weight:800;font-size:18px;")
        h.addWidget(logo)
        titles = QVBoxLayout()
        title = QLabel(APP_NAME)
        title.setObjectName("appTitle")
        subtitle = QLabel("E203 PUF 信任根 Dilithium2 后量子签名")
        subtitle.setObjectName("appSubtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        h.addLayout(titles)
        h.addStretch(1)
        self.chip_mode = self._chip("模式：—")
        self.chip_port = self._chip("串口：—")
        self.chip_key = self._chip("密钥：未生成")
        self.chip_fw = self._chip("固件：—")
        for c in (self.chip_mode, self.chip_port, self.chip_key, self.chip_fw):
            h.addWidget(c)
        h.addSpacing(10)
        self.lbl_busy = QLabel("空闲")
        self.lbl_busy.setObjectName("muted")
        h.addWidget(self.lbl_busy)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedWidth(100)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        h.addWidget(self.progress)
        self.lbl_conn = QLabel("● 未连接")
        self.lbl_conn.setStyleSheet(self._pill_style("#64748b", "#f1f5f9"))
        h.addWidget(self.lbl_conn)
        self.btn_theme = QPushButton("☾ 深色")
        self.btn_theme.clicked.connect(self._toggle_theme)
        h.addWidget(self.btn_theme)
        return header

    NAV_ITEMS = (
        ("演示首页", "一键演示与状态总览"),
        ("1 连接设备", "全链路仿真 / 硬件开发板"),
        ("2 固件下载", "入库与 SHA3-256 度量"),
        ("3 密钥生成", "PUF 挑战 / 直接种子"),
        ("4 签名与验证", "签名 验签 篡改演示"),
    )

    def _build_sidebar(self):
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(300)
        v = QVBoxLayout(side)
        v.setContentsMargins(0, 20, 0, 14)
        v.setSpacing(0)
        pal = self._pal()

        brand = QHBoxLayout()
        brand.setContentsMargins(20, 0, 20, 16)
        logo_path = os.path.join(BASE_DIR, "assets", "logo.png")
        logo = QLabel()
        logo.setFixedSize(38, 38)
        if os.path.exists(logo_path):
            logo.setPixmap(QPixmap(logo_path).scaled(38, 38, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo.setPixmap(make_icon("shieldcheck", pal["accent"], 34))
        brand.addWidget(logo)
        names = QVBoxLayout()
        names.setSpacing(0)
        n1 = QLabel("PUF × Dilithium")
        n1.setStyleSheet("font-size:16px;font-weight:800;")
        n2 = QLabel("可信启动演示平台")
        n2.setObjectName("navDesc")
        names.addWidget(n1)
        names.addWidget(n2)
        brand.addLayout(names)
        brand.addStretch(1)
        v.addLayout(brand)

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self._nav_rows = []
        for text, desc in self.NAV_ITEMS:
            item = QListWidgetItem(self.nav)
            item.setSizeHint(QSize(232, 52))
            row = QWidget()
            row.setObjectName("navRow")
            hl = QHBoxLayout(row)
            hl.setContentsMargins(12, 6, 10, 6)
            hl.setSpacing(10)
            bar = QFrame()
            bar.setFixedSize(4, 34)
            hl.addWidget(bar)
            tv = QVBoxLayout()
            tv.setSpacing(1)
            t = QLabel(text)
            t.setObjectName("navTitle")
            d = QLabel(desc)
            d.setObjectName("navDesc")
            tv.addWidget(t)
            tv.addWidget(d)
            hl.addLayout(tv, 1)
            self.nav.setItemWidget(item, row)
            self._nav_rows.append((row, bar, t))
        v.addWidget(self.nav, 1)

        stats = QFrame()
        stats.setObjectName("sideStats")
        sv = QVBoxLayout(stats)
        sv.setContentsMargins(22, 10, 18, 4)
        sv.setSpacing(6)
        cap = QLabel("本次会话")
        cap.setObjectName("navDesc")
        self.stat_verify = QLabel("验签次数  0")
        self.stat_last = QLabel("最近结果  —")
        self.stat_uptime = QLabel("运行时长  00:00")
        for lbl in (self.stat_verify, self.stat_last, self.stat_uptime):
            lbl.setObjectName("navDesc")
        sv.addWidget(cap)
        sv.addWidget(self.stat_verify)
        sv.addWidget(self.stat_last)
        sv.addWidget(self.stat_uptime)
        v.addWidget(stats)
        self._refresh_nav()
        return side

    def _refresh_nav(self):
        if not hasattr(self, "_nav_rows"):
            return
        pal = self._pal()
        current = self.nav.currentRow()
        for i, (row, bar, t) in enumerate(self._nav_rows):
            sel = i == current
            bg = pal["accent_bg"] if sel else "transparent"
            row.setStyleSheet(
                f"QWidget#navRow {{ background:{bg}; border-radius:10px; }}")
            bar.setStyleSheet(
                f"background:{pal['accent'] if sel else 'transparent'};"
                "border:none; border-radius:2px;")
            t.setStyleSheet(
                f"color:{pal['accent'] if sel else pal['text']}; font-weight:700;"
                "font-size:16px; border:none;")

    def _page(self, title):
        page = QWidget()
        h = QHBoxLayout(page)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        inner = QWidget()
        inner.setMaximumWidth(1900)
        v = QVBoxLayout(inner)
        v.setContentsMargins(0, 0, 0, 0)
        t = QLabel(title)
        t.setObjectName("pageTitle")
        v.addWidget(t)
        h.addWidget(inner)
        h.addStretch(1)
        return page, v

    @staticmethod
    def _card_title(layout, text):
        """分组框标题放进框内（不用 QGroupBox 自带的跨边框标题）。"""
        t = QLabel(text)
        t.setObjectName("cardTitle")
        layout.addWidget(t)
        return t

    def _scroll(self, page):
        """页面外包一层滚动区：内容超出可视高度时滚动，而不是压缩裁切。"""
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setWidget(page)
        return area

    # ------------------------------------------------------------------ 首页
    def _build_home_page(self):
        page, v = self._page("可信启动演示")
        hero = QFrame()
        hero.setObjectName("heroCard")
        self._shadow(hero)
        h = QHBoxLayout(hero)
        h.setContentsMargins(26, 22, 26, 22)
        left = QVBoxLayout()
        title = QLabel("四步完成一次完整演示")
        title.setStyleSheet("font-size:20px;font-weight:800;")
        self.lbl_home_device = QLabel("当前未连接设备")
        self.lbl_home_device.setObjectName("muted")
        left.addWidget(title)
        left.addWidget(self.lbl_home_device)
        badges = QHBoxLayout()
        badges.setSpacing(8)
        self.badge_fw = QLabel()
        self.badge_key = QLabel()
        self.badge_verdict = QLabel()
        for b in (self.badge_fw, self.badge_key, self.badge_verdict):
            b.setMinimumHeight(26)
            badges.addWidget(b)
        badges.addStretch(1)
        left.addLayout(badges)
        h.addLayout(left)
        h.addStretch(1)
        self.btn_demo = QPushButton("  一键开始演示")
        self.btn_demo.setObjectName("hero")
        self.btn_demo.setIcon(QIcon(make_icon("play", "#ffffff", 18)))
        self.btn_demo.setIconSize(QSize(18, 18))
        self.btn_demo.clicked.connect(self._demo)
        self._register_action(self.btn_demo)
        h.addWidget(self.btn_demo)
        v.addWidget(hero)
        v.addSpacing(14)

        chain_box = QGroupBox()
        c = QVBoxLayout(chain_box)
        self._card_title(c, "信任链流水线")
        chain = ChainWidget(self._pal)
        self.chains.append(chain)
        c.addWidget(chain)
        v.addWidget(chain_box)
        v.addStretch(1)
        self._refresh_badges()
        return page

    def _refresh_badges(self):
        if not hasattr(self, "badge_fw"):
            return
        pal = self._pal()

        def setb(lbl, text, kind):
            color_bg = {
                "ok": (pal["ok"], pal["ok_bg"]),
                "err": (pal["err"], pal["err_bg"]),
                "muted": (pal["muted"], pal["muted_bg"]),
            }[kind]
            lbl.setText(text)
            lbl.setStyleSheet(self._pill_style(*color_bg))

        setb(self.badge_fw, "固件已入库 ✓" if self.fw_digest else "固件未入库",
             "ok" if self.fw_digest else "muted")
        setb(self.badge_key, "密钥已生成 ✓" if self.pk_bytes else "密钥未生成",
             "ok" if self.pk_bytes else "muted")
        state = getattr(self, "_verdict_state", None)
        if state and state[0] is True:
            setb(self.badge_verdict, "上次验签 PASS ✓", "ok")
        elif state and state[0] is False:
            setb(self.badge_verdict, "上次验签 FAIL ✗", "err")
        else:
            setb(self.badge_verdict, "尚未验签", "muted")

    # ------------------------------------------------------------------ 连接
    def _build_connect_page(self):
        page, v = self._page("连接设备")
        cols = QHBoxLayout()
        cols.setSpacing(14)
        col_left = QVBoxLayout()
        col_right = QVBoxLayout()
        mode = QGroupBox()
        m = QVBoxLayout(mode)
        self._card_title(m, "运行方式")
        self.rb_xsim = QRadioButton("全链路仿真（RTL）")
        self.rb_ser = QRadioButton("硬件开发板")
        # radio 不进布局（仅作状态载体），必须用 QButtonGroup 显式互斥——
        # 无共同父控件的 radio 不互斥，会卡住导致选错后端
        self.backend_group = QButtonGroup(self)
        self.backend_group.setExclusive(True)
        for rb in (self.rb_xsim, self.rb_ser):
            rb.setVisible(False)
            self.backend_group.addButton(rb)
            rb.toggled.connect(self._backend_kind_changed)
        seg = QFrame()
        seg.setObjectName("segBar")
        sh = QHBoxLayout(seg)
        sh.setContentsMargins(4, 4, 4, 4)
        sh.setSpacing(4)
        self.seg_btns = []
        for text, rb in (("全链路仿真（RTL）", self.rb_xsim),
                         ("硬件开发板", self.rb_ser)):
            b = QPushButton(text)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setAutoExclusive(True)   # 互斥，杜绝选中态与隐藏 radio 脱节
            b.clicked.connect(lambda _c=False, r=rb: r.setChecked(True))
            sh.addWidget(b, 1)
            self.seg_btns.append(b)
        m.addWidget(seg)
        self.lbl_mode_desc = QLabel("")
        self.lbl_mode_desc.setObjectName("muted")
        m.addWidget(self.lbl_mode_desc)
        col_left.addWidget(mode)

        # 恢复上次选择的运行方式（选过一次就记住，重启不丢；兼容旧值 sim→xsim）
        saved = self.settings.get("backend", "xsim")
        saved = "xsim" if saved == "sim" else saved
        {"xsim": self.rb_xsim, "ser": self.rb_ser}.get(saved, self.rb_xsim).setChecked(True)

        conn = QGroupBox()
        c = QGridLayout(conn)
        ct = QLabel("连接设置")
        ct.setObjectName("cardTitle")
        c.addWidget(ct, 0, 0, 1, 5)
        c.addWidget(QLabel("串口（仅硬件开发板）"), 1, 0)
        self.cmb_port = QComboBox()
        self.cmb_port.setMinimumWidth(140)
        c.addWidget(self.cmb_port, 1, 1)
        self.btn_ref = QPushButton("刷新串口")
        self.btn_ref.clicked.connect(self._refresh_ports)
        c.addWidget(self.btn_ref, 1, 2)
        self.btn_conn = QPushButton("  连接设备")
        self.btn_conn.setObjectName("primary")
        self.btn_conn.setIcon(QIcon(make_icon("link", "#ffffff", 18)))
        self.btn_conn.setIconSize(QSize(18, 18))
        self.btn_conn.clicked.connect(self._connect)
        self._register_action(self.btn_conn)
        c.addWidget(self.btn_conn, 1, 3)
        c.setColumnStretch(4, 1)
        self.lbl_conn_help = QLabel("")
        self.lbl_conn_help.setObjectName("muted")
        c.addWidget(self.lbl_conn_help, 2, 0, 1, 4)
        col_left.addWidget(conn)

        self.gb_bringup = QGroupBox()
        bl = QVBoxLayout(self.gb_bringup)
        self._card_title(bl, "硬件拉板（等效 一键启动_真板演示.bat；仅硬件开发板模式）")
        brow = QHBoxLayout()
        self.btn_bringup = QPushButton("  一键拉板（清理残留 → 启动 openocd → 下载固件 + 串口自检）")
        self.btn_bringup.setObjectName("primary")
        self.btn_bringup.setIcon(QIcon(make_icon("chip", "#ffffff", 18)))
        self.btn_bringup.setIconSize(QSize(18, 18))
        self.btn_bringup.clicked.connect(self._bringup)
        self.btn_openocd_stop = QPushButton("停止 openocd")
        self.btn_openocd_stop.clicked.connect(self._stop_openocd)
        brow.addWidget(self.btn_bringup)
        brow.addWidget(self.btn_openocd_stop)
        brow.addStretch(1)
        bl.addLayout(brow)
        note = QLabel("过程输出显示在下方「设备实况」。换板 = 直接把连线换到另一块板即可，窗口无需改动；"
                      "自检串口使用左侧选中的 COM 口。拉板成功后再点「连接设备」。")
        note.setObjectName("muted")
        note.setWordWrap(True)
        bl.addWidget(note)
        col_left.addWidget(self.gb_bringup)
        col_left.addStretch(1)

        # 参数设置（原「用户操作说明」页迁入）
        box = QGroupBox()
        g = QGridLayout(box)
        st = QLabel("参数设置（保存后写入 settings.json）")
        st.setObjectName("cardTitle")
        g.addWidget(st, 0, 0, 1, 3)
        g.addWidget(QLabel("串口波特率"), 1, 0)
        self.cmb_baud = QComboBox()
        self.cmb_baud.addItems(["9600", "19200", "38400", "57600", "115200",
                                "230400", "460800", "921600"])
        self.cmb_baud.setCurrentText(str(self.settings.get("baud", 115200)))
        g.addWidget(self.cmb_baud, 1, 1)
        g.addWidget(QLabel("串口超时（秒）"), 2, 0)
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(1, 120)
        self.spin_timeout.setValue(int(self.settings.get("timeout", 10)))
        g.addWidget(self.spin_timeout, 2, 1)
        self.chk_tamper_random = QCheckBox("篡改位置随机（否则固定签名第 50 字节 / 固件第 0 字节）")
        self.chk_tamper_random.setChecked(bool(self.settings.get("tamper_random", True)))
        g.addWidget(self.chk_tamper_random, 3, 0, 1, 2)
        self.chk_dark = QCheckBox("深色模式")
        self.chk_dark.setChecked(self.dark)
        self.chk_dark.toggled.connect(lambda _on: self._toggle_theme()
                                      if _on != self.dark else None)
        g.addWidget(self.chk_dark, 4, 0, 1, 2)
        btn_row = QHBoxLayout()
        b_save = QPushButton("保存设置")
        b_save.setObjectName("primary")
        b_save.clicked.connect(self._save_settings)
        b_def = QPushButton("恢复默认")
        b_def.clicked.connect(self._default_settings)
        b_md = QPushButton("  导出演示报告")
        b_md.setIcon(QIcon(make_icon("doc", "#2a9d8f", 18)))
        b_md.setIconSize(QSize(18, 18))
        b_md.clicked.connect(lambda: self._export_report("md"))
        btn_row.addWidget(b_save)
        btn_row.addWidget(b_def)
        btn_row.addWidget(b_md)
        btn_row.addStretch(1)
        g.addLayout(btn_row, 5, 0, 1, 2)
        note = QLabel("波特率与超时将在下次连接时生效。")
        note.setObjectName("muted")
        g.addWidget(note, 6, 0, 1, 2)
        g.setColumnStretch(2, 1)
        col_right.addWidget(box)

        self.devlog_connect = DeviceLogView()
        self.devlog_views.append(self.devlog_connect)
        col_right.addWidget(self.devlog_connect)
        col_right.addStretch(1)
        cols.addLayout(col_left, 3)
        cols.addLayout(col_right, 2)
        v.addLayout(cols)
        v.addStretch(1)
        return page

    # -------------------------------------------------------------- 固件下载
    def _build_fw_page(self):
        page, v = self._page("固件下载")
        cols = QHBoxLayout()
        cols.setSpacing(14)
        col_left = QVBoxLayout()
        col_right = QVBoxLayout()

        self.gb_fw = QGroupBox()
        f = QVBoxLayout(self.gb_fw)
        self._card_title(f, "① 固件选择")
        self.lbl_fw = QLabel("当前：内置标准固件（2KB，00..FF 循环）—— 唯一正确件")
        self.lbl_fw.setWordWrap(True)
        f.addWidget(self.lbl_fw)
        note = QLabel("「内置标准固件」是唯一正确的固件（对应金样摘要）。"
                      "「选择外部固件文件」用于演示错误固件：加载后摘要会改变，"
                      "第 4 步验签将 FAIL——这就是系统识别错误固件的方式。")
        note.setObjectName("muted")
        note.setWordWrap(True)
        f.addWidget(note)
        buttons = QHBoxLayout()
        btn_pick = QPushButton("选择外部固件文件（错误固件演示）")
        btn_pick.clicked.connect(self._pick_fw)
        btn_builtin = QPushButton("恢复内置标准固件")
        btn_builtin.clicked.connect(self._builtin_fw)
        buttons.addWidget(btn_pick)
        buttons.addWidget(btn_builtin)
        buttons.addStretch(1)
        f.addLayout(buttons)
        col_left.addWidget(self.gb_fw)
        col_left.addStretch(1)

        dg = QGroupBox()
        d = QVBoxLayout(dg)
        self._card_title(d, "② 固件入库与 SHA3-256 度量")
        self.btn_fw = QPushButton("  上传并计算 SHA3-256")
        self.btn_fw.setObjectName("primary")
        self.btn_fw.setIcon(QIcon(make_icon("chip", "#ffffff", 18)))
        self.btn_fw.setIconSize(QSize(18, 18))
        self.btn_fw.clicked.connect(self._do_fw)
        self._register_action(self.btn_fw)
        d.addWidget(self.btn_fw)
        d.addWidget(QLabel("SHA3-256 摘要（256bit，完整显示）"))
        self.ed_sha = QPlainTextEdit()
        self.ed_sha.setReadOnly(True)
        self.ed_sha.setFont(MONO)
        self.ed_sha.setPlaceholderText("固件入库后显示完整 64 位十六进制摘要")
        self.ed_sha.setMinimumHeight(64)
        self.ed_sha.setMaximumHeight(80)
        d.addWidget(self.ed_sha)
        self.lbl_sha_cmp = QLabel("")
        self.lbl_sha_cmp.setObjectName("muted")
        self.lbl_sha_cmp.setWordWrap(True)
        d.addWidget(self.lbl_sha_cmp)
        col_right.addWidget(dg)
        col_right.addStretch(1)
        cols.addLayout(col_left, 1)
        cols.addLayout(col_right, 1)
        v.addLayout(cols)

        self.devlog_fw = DeviceLogView()
        self.devlog_views.append(self.devlog_fw)
        v.addWidget(self.devlog_fw)
        v.addStretch(1)
        return page

    # -------------------------------------------------------------- 密钥生成
    def _build_key_page(self):
        page, v = self._page("密钥生成")
        cols = QHBoxLayout()
        cols.setSpacing(14)
        col_left = QVBoxLayout()
        col_right = QVBoxLayout()

        self.gb_puf = QGroupBox()
        p = QVBoxLayout(self.gb_puf)
        self._card_title(p, "① 密钥来源与激励（挑战 256bit = 64 位十六进制）")
        line = QHBoxLayout()
        line.addWidget(QLabel("芯片"))
        self.cmb_dev = QComboBox()
        self.cmb_dev.addItems(["DEV0 (a5×32)", "DEV1 (5a×32)"])
        self.cmb_dev.currentIndexChanged.connect(self._dev_changed)
        line.addWidget(self.cmb_dev)
        line.addWidget(QLabel("密钥方式"))
        self.cmb_key_mode = QComboBox()
        self.cmb_key_mode.addItems(["PUF 挑战（CHAL）", "直接种子（SEED）"])
        line.addWidget(self.cmb_key_mode, 1)
        p.addLayout(line)
        seed_line = QHBoxLayout()
        self.ed_c = QLineEdit(DEFAULT_CHAL.hex())
        self.ed_c.setFont(MONO)
        self.ed_c.setMaxLength(64)
        self.ed_c.setCursorPosition(0)
        self.ed_c.textChanged.connect(self._challenge_edited)
        seed_line.addWidget(self.ed_c, 1)
        self.btn_rand = QPushButton("随机生成")
        self.btn_rand.clicked.connect(self._rand_chal)
        seed_line.addWidget(self.btn_rand)
        p.addLayout(seed_line)
        self.lbl_chal_bits = QLabel("")
        self.lbl_chal_bits.setObjectName("muted")
        p.addWidget(self.lbl_chal_bits)
        self._update_chal_bits()
        p.addWidget(QLabel("PUF 响应 R（256bit）"))
        self.ed_r = QLineEdit()
        self.ed_r.setReadOnly(True)
        self.ed_r.setFont(MONO)
        self.ed_r.setPlaceholderText("PUF 响应或 SEED 结果")
        p.addWidget(self.ed_r)
        self.b_kg = QPushButton("  生成密钥并读取 PUBK / PRIV")
        self.b_kg.setObjectName("primary")
        self.b_kg.setIcon(QIcon(make_icon("key", "#ffffff", 18)))
        self.b_kg.setIconSize(QSize(18, 18))
        self.b_kg.clicked.connect(self._do_keygen)
        self._register_action(self.b_kg)
        p.addWidget(self.b_kg)
        col_left.addWidget(self.gb_puf)
        col_left.addStretch(1)

        self.gb_keys = QGroupBox()
        k = QVBoxLayout(self.gb_keys)
        self._card_title(k, "② 密钥对（完整内容，可复制/导出）")
        k.addWidget(QLabel("PUBK 公钥（1312B）"))
        self.ed_pk = QPlainTextEdit()
        self.ed_pk.setReadOnly(True)
        self.ed_pk.setFont(MONO)
        self.ed_pk.setPlaceholderText("生成密钥后显示完整公钥")
        self.ed_pk.setMinimumHeight(120)
        k.addWidget(self.ed_pk, 2)
        row_pk = QHBoxLayout()
        cp = QPushButton("复制全部")
        cp.clicked.connect(lambda: QApplication.clipboard().setText(self.ed_pk.toPlainText()))
        ep = QPushButton("导出 .hex")
        ep.clicked.connect(lambda: self._export(self.ed_pk, "PUBK"))
        row_pk.addStretch(1)
        row_pk.addWidget(cp)
        row_pk.addWidget(ep)
        k.addLayout(row_pk)
        k.addWidget(QLabel("PRIV 私钥（2528B）"))
        self.ed_sk = QPlainTextEdit()
        self.ed_sk.setReadOnly(True)
        self.ed_sk.setFont(MONO)
        self.ed_sk.setPlaceholderText("生成密钥后显示完整私钥")
        self.ed_sk.setMinimumHeight(150)
        k.addWidget(self.ed_sk, 3)
        row_sk = QHBoxLayout()
        cs = QPushButton("复制全部")
        cs.clicked.connect(lambda: QApplication.clipboard().setText(self.ed_sk.toPlainText()))
        es = QPushButton("导出 .hex")
        es.clicked.connect(lambda: self._export(self.ed_sk, "PRIV"))
        row_sk.addStretch(1)
        row_sk.addWidget(cs)
        row_sk.addWidget(es)
        k.addLayout(row_sk)
        col_right.addWidget(self.gb_keys, 1)
        cols.addLayout(col_left, 2)
        cols.addLayout(col_right, 3)
        v.addLayout(cols, 1)

        self.devlog_key = DeviceLogView()
        self.devlog_views.append(self.devlog_key)
        v.addWidget(self.devlog_key)
        return page

    # -------------------------------------------------------------- 签名验证
    def _build_sign_page(self):
        page, v = self._page("签名与验证")
        cols = QHBoxLayout()
        cols.setSpacing(14)
        col_left = QVBoxLayout()
        col_right = QVBoxLayout()
        self.gb_alg = QGroupBox()
        self.gb_alg.setMinimumHeight(330)
        a = QVBoxLayout(self.gb_alg)
        self._card_title(a, "Dilithium2 主流程")
        actions = QHBoxLayout()
        self.b_sign = QPushButton("  生成签名（SIGN）")
        self.b_sign.setObjectName("primary")
        self.b_sign.setIcon(QIcon(make_icon("pen", "#ffffff", 18)))
        self.b_sign.setIconSize(QSize(18, 18))
        self.b_sign.clicked.connect(self._do_sign)
        self.b_ver = QPushButton("  验证签名（VERIFY）")
        self.b_ver.setIcon(QIcon(make_icon("check", "#2e8b6e", 18)))
        self.b_ver.setIconSize(QSize(18, 18))
        self.b_ver.clicked.connect(self._do_verify)
        self._register_action(self.b_sign)
        self._register_action(self.b_ver)
        actions.addWidget(self.b_sign)
        actions.addWidget(self.b_ver)
        a.addLayout(actions)

        # 验签大图卡：PASS 整卡变绿，FAIL 整卡变红并标注篡改位置，右侧摘要点阵
        self.verdict_card = QFrame()
        self.verdict_card.setMinimumHeight(216)
        self._shadow(self.verdict_card, blur=26, dy=5)
        vc = QHBoxLayout(self.verdict_card)
        vc.setContentsMargins(24, 16, 24, 16)
        vc.setSpacing(20)
        self.lbl_verdict_icon = QLabel()
        self.lbl_verdict_icon.setAlignment(Qt.AlignCenter)
        self.lbl_verdict_icon.setFixedSize(56, 56)
        vc.addWidget(self.lbl_verdict_icon, 0, Qt.AlignVCenter)
        texts = QVBoxLayout()
        texts.setSpacing(6)
        texts.addStretch(1)
        self.lbl_verdict = QLabel("—")
        self.lbl_verdict.setFont(BIG)
        self.lbl_verdict.setMinimumHeight(42)
        self.lbl_verdict_detail = QLabel("等待验签")
        self.lbl_verdict_detail.setMinimumHeight(22)
        self.lbl_verdict_tamper = QLabel("")
        self.lbl_verdict_tamper.setMinimumHeight(22)
        self.lbl_verdict_tamper.setVisible(False)
        texts.addWidget(self.lbl_verdict)
        texts.addWidget(self.lbl_verdict_detail)
        texts.addWidget(self.lbl_verdict_tamper)
        texts.addStretch(1)
        vc.addLayout(texts, 1)
        grid_box = QVBoxLayout()
        grid_box.setSpacing(4)
        grid_cap = QLabel("固件摘要点阵（SHA3-256，256bit）")
        grid_cap.setObjectName("muted")
        grid_cap.setAlignment(Qt.AlignCenter)
        self.digest_grid = BitGrid(self._pal)
        grid_box.addWidget(grid_cap)
        grid_box.addWidget(self.digest_grid, 0, Qt.AlignCenter)
        vc.addLayout(grid_box)
        a.addWidget(self.verdict_card)
        col_left.addWidget(self.gb_alg, 3)

        self.gb_sig = QGroupBox()
        sg = QVBoxLayout(self.gb_sig)
        self._card_title(sg, "签名数据（完整内容，可复制/导出）")
        self.ed_sig = QPlainTextEdit()
        self.ed_sig.setReadOnly(True)
        self.ed_sig.setFont(MONO)
        self.ed_sig.setPlaceholderText("签名生成后显示完整内容（2424B = 4848 位十六进制）")
        self.ed_sig.setMinimumHeight(110)
        sg.addWidget(self.ed_sig)
        row_sig = QHBoxLayout()
        csig = QPushButton("复制全部")
        csig.clicked.connect(lambda: QApplication.clipboard().setText(self.ed_sig.toPlainText()))
        esig = QPushButton("导出 .hex")
        esig.clicked.connect(lambda: self._export(self.ed_sig, "SIG"))
        row_sig.addStretch(1)
        row_sig.addWidget(csig)
        row_sig.addWidget(esig)
        sg.addLayout(row_sig)
        col_right.addWidget(self.gb_sig, 3)

        chain_box = QGroupBox()
        c = QVBoxLayout(chain_box)
        self._card_title(c, "信任链")
        chain = ChainWidget(self._pal)
        self.chains.append(chain)
        c.addWidget(chain)
        col_left.addWidget(chain_box)
        col_left.addStretch(1)

        tamper = QGroupBox()
        t = QVBoxLayout(tamper)
        self._card_title(t, "安全攻击演示（预期结果都是 FAIL）")
        self.btn_tamper_sig = QPushButton("  篡改签名 1 字节，再验签")
        self.btn_tamper_sig.setObjectName("danger")
        self.btn_tamper_sig.setIcon(QIcon(make_icon("alert", "#c23b3b", 18)))
        self.btn_tamper_sig.setIconSize(QSize(18, 18))
        self.btn_tamper_sig.clicked.connect(self._tamper_sig)
        self.btn_tamper_fw = QPushButton("  篡改固件 1 字节，再签名并验证")
        self.btn_tamper_fw.setObjectName("danger")
        self.btn_tamper_fw.setIcon(QIcon(make_icon("alert", "#c23b3b", 18)))
        self.btn_tamper_fw.setIconSize(QSize(18, 18))
        self.btn_tamper_fw.clicked.connect(self._tamper_fw)
        self._register_action(self.btn_tamper_sig)
        self._register_action(self.btn_tamper_fw)
        t.addWidget(self.btn_tamper_sig)
        t.addWidget(self.btn_tamper_fw)
        note = QLabel("说明：正常验签 PASS 才是正确结果；上面两个按钮是故意破坏后的演示，FAIL 才符合预期。"
                      "若未点篡改按钮却 FAIL，请检查密钥与固件状态。")
        note.setObjectName("muted")
        note.setWordWrap(True)
        t.addWidget(note)
        col_right.addWidget(tamper)
        col_right.addStretch(1)
        cols.addLayout(col_left, 3)
        cols.addLayout(col_right, 2)
        v.addLayout(cols, 1)

        self.devlog_sign = DeviceLogView()
        self.devlog_views.append(self.devlog_sign)
        v.addWidget(self.devlog_sign)
        v.addStretch(1)
        return page

    def _save_settings(self):
        self.settings.update({
            "baud": int(self.cmb_baud.currentText()),
            "timeout": self.spin_timeout.value(),
            "tamper_random": self.chk_tamper_random.isChecked(),
            "dark": self.dark,
        })
        save_settings(self.settings)
        self._log("SYS", "设置已保存到 settings.json")

    def _default_settings(self):
        self.cmb_baud.setCurrentText(str(DEFAULT_SETTINGS["baud"]))
        self.spin_timeout.setValue(DEFAULT_SETTINGS["timeout"])
        self.chk_tamper_random.setChecked(DEFAULT_SETTINGS["tamper_random"])
        self._save_settings()

    # -------------------------------------------------------------- 日志面板
    def _build_log_panel(self):
        self.log_panel = QFrame()
        self.log_panel.setObjectName("logPanel")
        v = QVBoxLayout(self.log_panel)
        v.setContentsMargins(12, 8, 12, 10)
        v.setSpacing(6)
        head = QHBoxLayout()
        title = QLabel("通信日志")
        title.setObjectName("logTitle")
        head.addWidget(title)
        head.addStretch(1)
        bclr = QPushButton("清空")
        bclr.clicked.connect(lambda: self.ed_log.clear())
        bsave = QPushButton("保存日志")
        bsave.clicked.connect(self._save_log)
        self.btn_log_toggle = QPushButton("收起 ▾")
        self.btn_log_toggle.clicked.connect(self._toggle_log)
        self._log_expanded = True
        for b in (bclr, bsave, self.btn_log_toggle):
            head.addWidget(b)
        v.addLayout(head)
        self.ed_log = QPlainTextEdit()
        self.ed_log.setReadOnly(True)
        self.ed_log.setFont(MONO)
        self.ed_log.setMaximumBlockCount(3000)
        self.ed_log.setMinimumHeight(110)
        v.addWidget(self.ed_log)
        return self.log_panel

    def _toggle_log(self):
        self._log_expanded = not self._log_expanded
        self.ed_log.setVisible(self._log_expanded)
        self.btn_log_toggle.setText("收起 ▾" if self._log_expanded else "展开 ▸")

    def _build_page_footer(self):
        col = QVBoxLayout()
        col.setSpacing(6)
        # 步骤进度行：RTL 长操作的估算进度 + 中途终止
        prog_row = QHBoxLayout()
        self.step_prog_lbl = QLabel("")
        self.step_prog_lbl.setObjectName("muted")
        self.step_prog = QProgressBar()
        self.step_prog.setRange(0, 100)
        self.step_prog.setTextVisible(True)
        self.step_prog.setFixedHeight(14)
        self.btn_abort = QPushButton("■ 终止当前操作")
        self.btn_abort.setObjectName("danger")
        self.btn_abort.clicked.connect(self._abort)
        prog_row.addWidget(self.step_prog_lbl)
        prog_row.addWidget(self.step_prog, 1)
        prog_row.addWidget(self.btn_abort)
        self.step_prog_lbl.setVisible(False)
        self.step_prog.setVisible(False)
        self.btn_abort.setVisible(False)
        col.addLayout(prog_row)
        row = QHBoxLayout()
        self.btn_prev = QPushButton("← 上一步")
        self.btn_prev.clicked.connect(lambda: self._step_page(-1))
        self.lbl_step_hint = QLabel("")
        self.lbl_step_hint.setObjectName("stepHint")
        self.lbl_step_hint.setAlignment(Qt.AlignCenter)
        self.btn_next = QPushButton("下一步 →")
        self.btn_next.clicked.connect(lambda: self._step_page(1))
        row.addWidget(self.btn_prev)
        row.addWidget(self.lbl_step_hint, 1)
        row.addWidget(self.btn_next)
        col.addLayout(row)
        return col

    # ------------------------------------------------------------------ 逻辑
    def _register_action(self, button):
        self._action_buttons.append(button)

    @staticmethod
    def _pill_style(color, background):
        return (f"QLabel {{ color:{color}; background:{background}; border-radius:11px; "
                "padding:5px 12px; font-weight:600; }")

    def _go_page(self, index):
        index = max(0, min(self.stack.count() - 1, index))
        self.stack.setCurrentIndex(index)
        if self.nav.currentRow() != index:
            self.nav.blockSignals(True)
            self.nav.setCurrentRow(index)
            self.nav.blockSignals(False)
        self._refresh_nav()
        self.btn_prev.setEnabled(index > 0)
        self.btn_next.setEnabled(index < self.stack.count() - 1)
        self.lbl_step_hint.setText(self.PAGE_HINTS[index])

    def _step_page(self, delta):
        self._go_page(self.stack.currentIndex() + delta)

    def _refresh_ports(self):
        current = self.cmb_port.currentText()
        self.cmb_port.clear()
        try:
            ports = SerialBackend.list_ports()
            self.cmb_port.addItems(ports)
            if current in ports:
                self.cmb_port.setCurrentText(current)
            elif ports:
                self.cmb_port.setCurrentIndex(0)
            if hasattr(self, "ed_log"):
                self._log("SYS", "串口刷新：" + ("、".join(ports) if ports
                          else "未检测到串口（请检查 USB 连接后再点「刷新串口」）"))
        except Exception as e:
            if hasattr(self, "ed_log"):
                self._log("ERR", f"串口枚举失败：{e}")

    def _log(self, tag, text):
        line = f"[{ts()}] [{tag}] {text}"
        self.ed_log.appendPlainText(line)
        sb = self.ed_log.verticalScrollBar()
        sb.setValue(sb.maximum())
        # 真板串口流与拉板过程同步到各页底部「设备实况」（RTL 由 console tail 覆盖）
        views = getattr(self, "devlog_views", None)
        if views and (tag == "BRINGUP"
                      or (isinstance(self.backend, SerialBackend)
                          and tag in ("PC", "PC>", "FPGA"))):
            for view in views:
                view.append_lines([line])

    def _on_step(self, name):
        """Worker 步骤信号：同步信任链流水线高亮与页面分组描边。"""
        chain_idx = {"measure": 0, "puf": 1, "keygen": 2, "sign": 3, "verify": 4}
        if name in chain_idx:
            for chain in self.chains:
                chain.set_running(chain_idx[name])
        for key, group in self.gb.items():
            group.setProperty("active", key == name)
            group.style().unpolish(group)
            group.style().polish(group)

    def _chain_verdict(self, ok):
        for chain in self.chains:
            chain.set_state(4, "done" if ok else "fail")

    def _chain_fail_current(self):
        for chain in self.chains:
            for i, state in enumerate(chain.states):
                if state == "running":
                    chain.set_state(i, "fail")
                    break

    def _refresh_chips(self):
        if not hasattr(self, "chip_mode"):
            return
        pal = self._pal()
        if self.backend is not None:
            mode = getattr(self.backend, "name", "设备")
        elif self.rb_ser.isChecked():
            mode = "硬件开发板"
        else:
            mode = "全链路仿真（RTL）"
        self.chip_mode.setText("模式：" + mode)
        port = self.cmb_port.currentText() if self.rb_ser.isChecked() else ""
        self.chip_port.setText("串口：" + (port or "—"))
        self.chip_key.setText("密钥：" + ("已生成 ✓" if self.pk_bytes else "未生成"))
        self.chip_key.setStyleSheet(self._pill_style(
            *( (pal["ok"], pal["ok_bg"]) if self.pk_bytes else (pal["muted"], pal["muted_bg"]) )))
        self.chip_fw.setText("固件：" + ((self.fw_digest[:16] + "…") if self.fw_digest else "—"))
        self.chip_fw.setStyleSheet(self._pill_style(
            *( (pal["ok"], pal["ok_bg"]) if self.fw_digest else (pal["muted"], pal["muted_bg"]) )))
        self.chip_mode.setStyleSheet(self._chip_style())
        self.chip_port.setStyleSheet(self._chip_style())

    def _set_verdict(self, ok, ms=None, tamper=None):
        """验签大图卡：PASS 整卡变绿，FAIL 整卡变红并标注篡改位置。"""
        self._verdict_state = None if ok is None else (ok, ms, tamper)
        pal = self._pal()
        if ok is True:
            text, icon, grid_state = "0 = PASS", "shieldcheck", "done"
            color, bg, border = pal["ok"], pal["ok_bg"], pal["ok_border"]
        elif ok is False:
            text, icon, grid_state = "1 = FAIL", "alert", "fail"
            color, bg, border = pal["err"], pal["err_bg"], pal["err_border"]
        else:
            text, icon, grid_state = "—", "shield", "idle"
            color, bg, border = pal["muted"], pal["card"], pal["border"]
        self.verdict_card.setStyleSheet(
            f"QFrame {{ background:{bg}; border:2px solid {border}; border-radius:14px; }}")
        self.lbl_verdict_icon.setText("")
        self.lbl_verdict_icon.setStyleSheet("border:none;")
        self.lbl_verdict_icon.setPixmap(make_icon(icon, color, 48))
        self.lbl_verdict.setText(text)
        self.lbl_verdict.setStyleSheet(f"color:{color}; border:none;")
        if ok is None:
            detail = "等待验签"
        else:
            parts = []
            if ms is not None:
                parts.append(f"验签耗时 {ms:.0f} ms")
            if self.fw_digest:
                parts.append(f"固件摘要 {self.fw_digest[:16]}…")
            detail = "，".join(parts) or "—"
            if ok is True:
                detail = "【正常验签通过】" + detail
            elif tamper:
                detail = "【符合预期：防篡改演示 FAIL】" + detail
            else:
                detail = "【异常：未篡改却验签 FAIL，请检查密钥/固件状态后重试】" + detail
        self.lbl_verdict_detail.setText(detail)
        self.lbl_verdict_detail.setStyleSheet(f"color:{pal['muted']}; border:none;")
        hl_byte = -1
        if ok is False and tamper:
            self.lbl_verdict_tamper.setText(f"!! 检测到篡改 —— 篡改位置：{tamper}")
            self.lbl_verdict_tamper.setVisible(True)
            if self._last_tamper and self._last_tamper[0] == "签名" \
                    and self._last_tamper[1] < 32:
                hl_byte = self._last_tamper[1]
        else:
            self.lbl_verdict_tamper.setVisible(False)
        self.lbl_verdict_tamper.setStyleSheet(
            f"color:{pal['err']}; font-weight:700; font-size:15px; border:none;")
        digest_bytes = None
        if self.fw_digest:
            try:
                digest_bytes = bytes.fromhex(self.fw_digest)
            except ValueError:
                pass
        self.digest_grid.set_bits(digest_bytes, grid_state, hl_byte)
        if ok is not None:
            self.stat_verify.setText(f"验签次数  {self.verify_count}")
            self.stat_last.setText("最近结果  " + ("PASS ✓" if ok else "FAIL ✗"))
            self.stat_last.setStyleSheet(f"color:{color}; font-size:12px;")
        self._refresh_badges()

    def _set_conn_state(self, state, detail=""):
        pal = self._pal()
        styles = {
            "disconnected": ("● 未连接", pal["muted"], pal["muted_bg"], "未连接"),
            "connecting": ("● 连接中", pal["warn"], pal["warn_bg"], "正在建立连接…"),
            "ready": ("● 已连接", pal["ok"], pal["ok_bg"], "设备已就绪"),
            "error": ("● 连接失败", pal["err"], pal["err_bg"], "连接失败"),
        }
        pill, color, bg, big = styles[state]
        self.lbl_conn.setText(pill)
        self.lbl_conn.setStyleSheet(self._pill_style(color, bg))
        if state == "ready":
            backend_name = getattr(self.backend, "name", "设备")
            port = self.cmb_port.currentText() if isinstance(self.backend, SerialBackend) else ""
            detail = backend_name + (f"（{port}，{self.settings.get('baud', 115200)} 8N1）" if port else "")
            self.lbl_home_device.setText("当前设备：" + detail)
        else:
            self.lbl_home_device.setText("当前状态：" + big)
        self._refresh_chips()

    def _backend_kind_changed(self):
        if not hasattr(self, "cmb_dev"):
            return
        ser = self.rb_ser.isChecked()
        xsim = self.rb_xsim.isChecked()
        locked = self._is_busy or self.backend is not None
        for rb in (self.rb_xsim, self.rb_ser):
            rb.setEnabled(not locked)
        if hasattr(self, "seg_btns"):
            for b, rb in zip(self.seg_btns, (self.rb_xsim, self.rb_ser)):
                b.setChecked(rb.isChecked())
                b.setEnabled(not locked)
            self.lbl_mode_desc.setText(
                "通过串口连接 FPGA 板卡，需固件已运行（先拉板）" if ser else
                "界面自动拉起 Vivado xsim 跑真实 RTL，速度较慢（全流程约 41 分钟）")
        self.cmb_port.setEnabled(ser and not locked)
        self.btn_ref.setEnabled(ser and not locked)
        no_port = False
        if ser and not locked:
            # 切到硬件开发板时自动刷新串口：板子后插也能看到
            if self.cmb_port.count() == 0:
                self._refresh_ports()
            no_port = self.cmb_port.count() == 0
        if hasattr(self, "gb_bringup"):
            self.gb_bringup.setVisible(ser)
        if xsim:
            self.cmb_dev.setCurrentIndex(0)
        self.cmb_dev.setEnabled(not xsim and not self._is_busy)
        self.cmb_dev.setToolTip("RTL 桥当前固定 DEV0" if xsim else "")
        kind = "ser" if ser else "xsim"
        if getattr(self, "_last_backend_kind", None) != kind:
            self.cmb_key_mode.setCurrentIndex(1 if ser else 0)
            if getattr(self, "_last_backend_kind", None) is not None:
                name = {"xsim": "全链路仿真（RTL，真实 RTL 逐拍，分钟级）",
                        "ser": "硬件开发板（串口）"}[kind]
                self._log("SYS", f"运行方式已切换为：{name}")
                self.settings["backend"] = kind
                save_settings(self.settings)
            self._last_backend_kind = kind
        if ser:
            help_text = ("未检测到串口：请确认板子 USB 已插好，再点「刷新串口」。"
                         if no_port else
                         f"板卡固件需已运行（先点上方「一键拉板」）；波特率 "
                         f"{self.settings.get('baud', 115200)} 8N1。")
        else:
            help_text = "首次连接可能包含编译；后续各步骤耗时较长属于正常现象。"
        self.lbl_conn_help.setText(help_text)
        self._refresh_chips()

    def _connect(self):
        if self._is_busy:
            return
        if self.backend:
            backend = self.backend
            self.backend = None
            try:
                backend.close()
            except Exception as e:
                self._log("ERR", f"断开清理异常：{e}")
            self.btn_conn.setText("连接设备")
            self._set_conn_state("disconnected")
            self._clear_session()
            self._backend_kind_changed()
            self._log("SYS", "已断开")
            self._report_add("断开连接", "", "—")
            return

        kind = ("硬件开发板（串口）" if self.rb_ser.isChecked()
                else "全链路仿真（RTL，Vivado xsim 真实 RTL，分钟级）")
        self._log("SYS", f"连接请求：运行方式 = {kind}")
        if self.force_sim:
            backend = SimBackend(self._log_from_worker, self._dev(), fast=True)
        elif self.rb_xsim.isChecked():
            backend = XsimBackend(self._log_from_worker)
            self._log("SYS", "RTL 仿真：首次连接可能包含编译，后续步骤较慢。")
        else:
            port = self.cmb_port.currentText()
            if not port:
                self._demo_after_connect = False
                QMessageBox.warning(self, "真实串口", "请先选择 COM 口")
                return
            try:
                backend = SerialBackend(self._log_from_worker, port,
                                        timeout=float(self.settings.get("timeout", 10)),
                                        baud=int(self.settings.get("baud", 115200)))
            except Exception as e:
                self._set_conn_state("error", str(e))
                QMessageBox.critical(self, "真实串口", f"打开失败：{e}")
                return

        self.backend = backend
        self._connecting = True
        self.btn_conn.setText("断开连接")
        self._set_conn_state("connecting")
        self._backend_kind_changed()
        self._run(self._open_sync, busy="连接并同步设备", on_done=self._connect_ready)

    def _open_sync(self, w):
        self.backend.open()
        return self.backend.sync()

    def _connect_ready(self, _result=None):
        self._connecting = False
        self._set_conn_state("ready")
        self._backend_kind_changed()
        self._log("SYS", "连接与 HELP 同步完成")
        self._report_add("连接设备", self._mode_desc(), "成功")
        if isinstance(self.backend, XsimBackend):
            pids = getattr(self.backend, "xsim_pids", [])
            self._log("SYS", f"真实 RTL 仿真已拉起并经进程核验：xsim pid={pids}。"
                             "本模式每一步都是 RTL 逐拍计算，全流程约 41 分钟；"
                             "若秒级出结果则说明后端不是 RTL，请检查运行方式选择。")
            from xsim_link import CONSOLE_LOG
            self._console_off = 0
            for view in self.devlog_views:
                view.set_caption(f"设备实况：xsim console 实时输出（{CONSOLE_LOG}）")
        elif isinstance(self.backend, SerialBackend):
            for view in self.devlog_views:
                view.set_caption("设备实况：串口收发实时回显")
        if self._demo_after_connect:
            self._demo_after_connect = False
            self._demo()

    def _connect_failed(self, backend):
        self._connecting = False
        self._demo_after_connect = False
        if self.backend is backend:
            try:
                backend.close()
            except Exception:
                pass
            self.backend = None
        self.btn_conn.setText("连接设备")
        self._set_conn_state("error", "请检查设备、串口和固件状态后重试。")
        self._backend_kind_changed()

    def _dev(self):
        return "DEV0" if self.cmb_dev.currentIndex() == 0 else "DEV1"

    def _dev_changed(self, _):
        if isinstance(self.backend, SimBackend):
            self.backend.dev = self._dev()
            self._log("SYS", f"仿真芯片切换为 {self._dev()}（下次生成密钥生效）")
        self._clear_keys()

    def _rand_chal(self):
        self.ed_c.setText(bytes(random.randrange(256) for _ in range(32)).hex())

    def _update_chal_bits(self):
        """激励输入旁的 bit 计数器：实时显示已输入/还差多少。"""
        text = self.ed_c.text().strip()
        n = len(text)
        bits = n * 4
        pal = self._pal()
        if n == 64 and all(c in "0123456789abcdefABCDEF" for c in text):
            self.lbl_chal_bits.setText(f"已输入 64/64 位十六进制 = 256/256 bit ✓ 完整")
            self.lbl_chal_bits.setStyleSheet(f"color:{pal['ok']}; font-weight:600;")
        else:
            bad = "" if all(c in "0123456789abcdefABCDEF" for c in text) else "（含非 hex 字符）"
            self.lbl_chal_bits.setText(
                f"已输入 {n}/64 位十六进制 = {bits}/256 bit，还差 {64 - n} 位（{(64 - n) * 4} bit）{bad}")
            self.lbl_chal_bits.setStyleSheet(f"color:{pal['err']}; font-weight:600;")

    def _challenge_edited(self):
        self._update_chal_bits()
        self._clear_keys()

    def _log_from_worker(self, tag, text):
        worker = self.worker
        if worker is not None:
            worker.log.emit(tag, text)
        else:
            self._log(tag, text)

    def _run(self, fn, busy="", on_done=None):
        if self.worker is not None and self.worker.isRunning():
            return
        self.worker = worker = Worker(fn)
        worker.log.connect(self._log)
        worker.step.connect(self._on_step)
        worker.result.connect(self._on_result)
        worker.failed.connect(self._on_worker_failed)
        if on_done:
            worker.finished_ok.connect(on_done)
        worker.finished.connect(lambda: self._busy(False))
        self._busy(True, busy)
        worker.start()

    def _on_worker_failed(self, error):
        self._log("ERR", error)
        self._chain_fail_current()
        if "用户终止" in error:
            self._report_add("终止操作", "", "用户中途终止")
            return                       # 用户主动终止不弹错误框
        self._report_add("操作失败", "", error[:120])
        if self._connecting and self.backend is not None:
            self._connect_failed(self.backend)
        QMessageBox.critical(self, "操作失败", error)

    # RTL 各步骤历史实测耗时（秒），用于估算进度条（机器繁忙时可能更慢，仅供参考）
    RTL_ESTIMATES = {
        "连接并同步设备": 90,
        "固件入库与 SHA3-256 度量": 30 * 60,
        "生成并读取 Dilithium2 密钥对": 12 * 60,
        "Dilithium2 签名": 8 * 60,
        "Dilithium2 验签": 15 * 60,
        "篡改固件并验证": 70 * 60,
        "篡改签名并验证": 20 * 60,
        "一键演示全流程": 55 * 60,
        "硬件拉板": 180,
    }

    def _busy(self, on, text=""):
        self._is_busy = on
        for button in self._action_buttons:
            button.setEnabled(not on)
        self.lbl_busy.setText(("忙碌：" + text) if on else "空闲")
        self.lbl_busy.setStyleSheet("color:#c98a1e;font-weight:600;" if on
                                    else f"color:{self._pal()['muted']};")
        self.progress.setVisible(on)
        # 步骤进度条 + 终止按钮（RTL 长操作才有意义，其他后端显示不定进度）
        is_rtl = isinstance(self.backend, XsimBackend)
        self._step_t0 = time.time()
        self._step_est = self.RTL_ESTIMATES.get(text) if is_rtl else None
        self.step_prog.setVisible(on)
        self.step_prog_lbl.setVisible(on)
        self.btn_abort.setVisible(on)
        if on:
            self.step_prog_lbl.setText(text)
            if self._step_est:
                self.step_prog.setRange(0, 100)
                self.step_prog.setValue(0)
            else:
                self.step_prog.setRange(0, 0)      # 无估算 → 不定进度
        if not on and self._aborted:
            # 终止收尾：后端已被 abort，直接复位连接状态
            self._aborted = False
            self.backend = None
            self.btn_conn.setText("连接设备")
            self._set_conn_state("disconnected", "已终止。仿真进程与信箱残留已清理，可重新连接。")
            self._backend_kind_changed()
            self._log("SYS", "已终止并清理完毕")
        self._backend_kind_changed()

    def _tick_step_progress(self):
        if not self._is_busy:
            return
        if self._step_est:
            el = time.time() - self._step_t0
            pct = min(99, int(el / self._step_est * 100))
            self.step_prog.setValue(pct)
            fmt = lambda s: f"{int(s) // 60:02d}:{int(s) % 60:02d}"
            self.step_prog_lbl.setText(
                f"{self.lbl_busy.text()[3:]}｜已用 {fmt(el)} / 预计约 {fmt(self._step_est)}")

    def _abort(self):
        """用户点「终止当前操作」：立即中止后端并清理仿真遗物。"""
        if not self._is_busy:
            return
        self._aborted = True
        self._log("SYS", "正在终止：中断等待并清理仿真进程…")
        be = self.backend
        if be is not None and hasattr(be, "abort"):
            try:
                be.abort()
            except Exception as e:
                self._log("ERR", f"终止清理异常：{e}")

    # ------------------------------------------------------------ 设备实况
    def _poll_device_log(self):
        """1s 轮询：RTL 模式把 xsim console 新增内容推到各页底部「设备实况」。"""
        if not isinstance(self.backend, XsimBackend):
            return
        from xsim_link import CONSOLE_LOG
        try:
            size = os.path.getsize(CONSOLE_LOG)
        except OSError:
            return
        if size < self._console_off:         # 文件被重建（重新连接）
            self._console_off = 0
        if size == self._console_off:
            return
        try:
            with open(CONSOLE_LOG, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._console_off)
                data = f.read()
                self._console_off = f.tell()
        except OSError:
            return
        lines = [ln for ln in data.replace("\r\n", "\n").replace("\r", "\n").split("\n")
                 if ln.strip()]
        for view in self.devlog_views:
            view.append_lines(lines)

    # ------------------------------------------------------------ 硬件拉板
    def _bringup(self):
        """等效 一键启动_真板演示.bat：清残留 → 起 openocd → board_bringup.py 自检。"""
        if self._is_busy:
            return
        if self.backend is not None:
            # 已连接时串口被本界面占用，board_bringup 自检会打不开 COM 口——先断开
            self._connect()
            self._log("SYS", "拉板前已自动断开连接（释放串口）。")
        if self._openocd_proc is not None and self._openocd_proc.poll() is None:
            QMessageBox.information(self, "拉板", "openocd 已在运行（pid=%d）。"
                                    "如需重拉，先点「停止 openocd」。" % self._openocd_proc.pid)
            return

        def fn(w):
            taskkill = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                                    "System32", "taskkill.exe")
            w.log.emit("LINK", "[0/3] 清理残留 openocd/gdb 进程…")
            for img in ("openocd.exe", "riscv-nuclei-elf-gdb.exe"):
                subprocess.run([taskkill, "/F", "/IM", img],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1)
            w.log.emit("LINK", "[1/3] 启动 openocd 服务…")
            ocd_dir = r"D:\FPGA\NucleiStudio\NucleiStudio\toolchain\openocd\bin"
            ocd_log = open(r"D:\FPGA\sim_logs\openocd_gui.log", "w", errors="replace")
            # Windows 下 CreateProcess 不会在子进程 cwd 里找可执行文件，必须给全路径
            proc = subprocess.Popen(
                [os.path.join(ocd_dir, "openocd.exe"),
                 "-f", "../scripts/board/nuclei-demosoc-v2.cfg"],
                cwd=ocd_dir, stdout=ocd_log, stderr=subprocess.STDOUT)
            self._openocd_proc = proc
            w.log.emit("LINK", f"openocd pid={proc.pid}（日志：sim_logs/openocd_gui.log）")
            time.sleep(2)
            if proc.poll() is not None:
                raise RuntimeError(f"openocd 启动即退出 rc={proc.returncode}，"
                                   "检查调试器 USB 是否插好；日志见 sim_logs/openocd_gui.log")
            w.log.emit("LINK", "[2/3] 下载固件并串口自检（board_bringup.py）…")
            port = self.cmb_port.currentText() or "COM3"
            r = subprocess.Popen([sys.executable,
                                  r"D:\FPGA\Dilithium-master\board_bringup.py", port],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, errors="replace")
            for line in r.stdout:
                line = line.rstrip()
                if line:
                    w.log.emit("BRINGUP", line)
            rc = r.wait()
            if rc != 0:
                raise RuntimeError(
                    "拉板自检失败（board_bringup rc=%d）。常见处置："
                    "卡在 openocd → 拔插调试器 USB；PUF 超时 → 拔 PUF 板 3V3 线 10 秒后重插再试。" % rc)
            return port

        def done(port):
            self._log("SYS", f"拉板完成，自检通过（串口 {port}）。现在可以点「连接设备」。")
            self._report_add("一键拉板", port, "成功")
        self._run(fn, "硬件拉板", on_done=done)

    def _stop_openocd(self):
        proc = self._openocd_proc
        self._openocd_proc = None
        if proc is not None and proc.poll() is None:
            taskkill = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                                    "System32", "taskkill.exe")
            try:
                subprocess.run([taskkill, "/F", "/T", "/PID", str(proc.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=15)
            except Exception:
                pass
            self._log("SYS", "openocd 已停止")
        else:
            self._log("SYS", "openocd 未在运行")

    # -------------------------------------------------------------- 结果分发
    def _on_result(self, key, val):
        if key == "sha":
            self.ed_sha.setPlainText(val)
            self.fw_digest = val
            import hashlib
            golden = hashlib.sha3_256(builtin_firmware()).hexdigest()
            if val == golden:
                self.lbl_sha_cmp.setText("✓ 与标准固件本地摘要（PC 侧 hashlib 计算）逐字节一致 —— 固件正确")
                self.lbl_sha_cmp.setStyleSheet(f"color:{self._pal()['ok']}; font-weight:600;")
            else:
                self.lbl_sha_cmp.setText(
                    f"✗ 与标准固件摘要不一致！标准固件金样：{golden} —— 当前固件不是标准件，后续验签将 FAIL")
                self.lbl_sha_cmp.setStyleSheet(f"color:{self._pal()['err']}; font-weight:600;")
            self._refresh_chips()
            self._refresh_badges()
        elif key == "r":
            self.ed_r.setText(val)
            self.ed_r.setCursorPosition(0)
        elif key == "pk":
            self.ed_pk.setPlainText(val)
            try:
                self.pk_bytes = bytes.fromhex(val)
            except ValueError:
                pass
            self._refresh_chips()
            self._refresh_badges()
        elif key == "sk":
            self.ed_sk.setPlainText(val)
        elif key == "sig":
            self.ed_sig.setPlainText(val)
            try:
                self.sig_wire = bytes.fromhex(val)
            except ValueError:
                pass
        elif key == "verdict":
            ok, ms, tamper = val
            self.verify_count += 1
            if ok:
                self.pass_count += 1
            self.verify_times.append(ms)
            self._set_verdict(ok, ms, tamper)
            self._chain_verdict(ok)

    # -------------------------------------------------------------- 报告导出
    def _mode_desc(self):
        if self.backend is None:
            return "未连接"
        name = getattr(self.backend, "name", "设备")
        if isinstance(self.backend, SerialBackend):
            name += f"（{self.cmb_port.currentText()}）"
        return name

    def _report_add(self, op, detail, result):
        self.report.append({
            "time": ts(), "mode": self._mode_desc(),
            "op": op, "detail": detail, "result": result,
        })

    def _pk_fingerprint(self):
        if not self.pk_bytes:
            return "—"
        import hashlib
        return hashlib.sha256(self.pk_bytes).hexdigest()[:32]

    def _export_report(self, fmt):
        if not self.report:
            QMessageBox.information(self, "报告", "暂无可导出的事件，请先运行演示。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出演示报告", f"demo_report.{fmt}",
            "Markdown (*.md)" if fmt == "md" else "CSV (*.csv)")
        if not path:
            return
        stats = (f"{self.pass_count}/{self.verify_count} PASS"
                 if self.verify_count else "未验签")
        avg = (f"{sum(self.verify_times) / len(self.verify_times):.1f} ms"
               if self.verify_times else "—")
        if fmt == "md":
            lines = [
                "# PUF × Dilithium 可信启动演示报告",
                "",
                f"- 生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"- 运行模式：{self._mode_desc()}",
                f"- 固件摘要（SHA3-256）：{self.fw_digest or '—'}",
                f"- 公钥指纹（SHA-256 前 16B）：{self._pk_fingerprint()}",
                f"- 验签统计：{stats}，平均耗时 {avg}",
                "",
                "| 时间 | 操作 | 详情 | 结果 |",
                "| --- | --- | --- | --- |",
            ]
            for e in self.report:
                lines.append(f"| {e['time']} | {e['op']} | {e['detail']} | {e['result']} |")
            content = "\n".join(lines) + "\n"
        else:
            import io
            buf = io.StringIO()
            wcsv = csv.writer(buf)
            wcsv.writerow(["生成时间", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
            wcsv.writerow(["运行模式", self._mode_desc()])
            wcsv.writerow(["固件摘要(SHA3-256)", self.fw_digest or "—"])
            wcsv.writerow(["公钥指纹(SHA-256前16B)", self._pk_fingerprint()])
            wcsv.writerow(["验签统计", stats])
            wcsv.writerow(["平均验签耗时", avg])
            wcsv.writerow([])
            wcsv.writerow(["时间", "操作", "详情", "结果"])
            for e in self.report:
                wcsv.writerow([e["time"], e["op"], e["detail"], e["result"]])
            content = buf.getvalue()
        with open(path, "w", encoding="utf-8-sig" if fmt == "csv" else "utf-8",
                  newline="") as f:
            f.write(content)
        self._log("SYS", f"报告已导出：{path}")

    # -------------------------------------------------------------- 固件密钥
    def _pick_fw(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 2KB 固件文件（错误固件演示用）")
        if not path:
            return
        with open(path, "rb") as f:
            data = f.read()
        if len(data) != 2048:
            QMessageBox.warning(self, "固件", f"需恰好 2048B，当前 {len(data)}B")
            return
        self.fw_bytes = data
        self.lbl_fw.setText("当前：外部文件 " + os.path.basename(path) + "（非标准固件，验签将 FAIL）")
        self._clear_firmware_results()
        self._log("SYS", f"载入固件 {path}")

    def _builtin_fw(self):
        self.fw_bytes = builtin_firmware()
        self.lbl_fw.setText("当前：内置标准固件（2KB，00..FF 循环）—— 唯一正确件")
        self._clear_firmware_results()

    def _clear_firmware_results(self):
        self.ed_sha.clear()
        self.lbl_sha_cmp.setText("")
        self.ed_sig.clear()
        self.sig_wire = None
        self.fw_digest = None
        self._last_tamper = None
        self._set_verdict(None)
        for chain in self.chains:
            chain.reset()
        self._refresh_chips()

    def _clear_keys(self):
        if not hasattr(self, "ed_pk"):
            return
        self.ed_r.clear()
        self.ed_pk.clear()
        self.ed_sk.clear()
        self.ed_sig.clear()
        self.sig_wire = None
        self.pk_bytes = None
        self._last_tamper = None
        self._set_verdict(None)
        for chain in self.chains:
            chain.reset()
        self._refresh_chips()

    def _clear_session(self):
        self._clear_firmware_results()
        self._clear_keys()
        self.verify_count = 0
        self.pass_count = 0
        self.verify_times = []
        self.stat_verify.setText("验签次数  0")
        self.stat_last.setText("最近结果  —")
        self.stat_last.setStyleSheet("")

    def _need_be(self):
        if not self.backend:
            QMessageBox.information(self, "提示", "请先到“连接设备”页面建立连接")
            self._go_page(1)
            return False
        return True

    def _chal_bytes(self):
        text = self.ed_c.text().strip()
        if len(text) != 64:
            raise ValueError("挑战/种子须为 64 hex（256bit）")
        return bytes.fromhex(text)

    def _use_seed(self):
        return self.cmb_key_mode.currentIndex() == 1

    def _do_fw(self):
        if not self._need_be():
            return
        firmware = self.fw_bytes
        self.ed_sig.clear()
        self.sig_wire = None
        self._set_verdict(None)

        def fn(w):
            w.step.emit("measure")
            digest = self.backend.fw(firmware)
            w.result.emit("sha", digest.hex())
            return digest.hex()
        self._run(fn, "固件入库与 SHA3-256 度量",
                  on_done=lambda sha: self._report_add(
                      "固件入库", f"{len(self.fw_bytes)} B", "SHA3 " + sha[:16] + "…"))

    def _do_keygen(self):
        if not self._need_be():
            return
        try:
            challenge = self._chal_bytes()
        except Exception as e:
            QMessageBox.warning(self, "输入有误", str(e))
            return
        use_seed = self._use_seed()
        self._clear_keys()

        def fn(w):
            w.step.emit("puf")
            if use_seed:
                self.backend.seed(challenge)
                w.result.emit("r", challenge.hex())
            else:
                response = self.backend.chal(challenge)
                w.result.emit("r", response.hex() if response is not None
                              else "R 在设备侧生成，PC 不可见")
            w.step.emit("keygen")
            pk = self.backend.pubk()
            if pk:
                w.result.emit("pk", pk.hex())
            sk = self.backend.priv()
            if sk:
                w.result.emit("sk", sk.hex())
            return use_seed
        self._run(fn, "生成并读取 Dilithium2 密钥对",
                  on_done=lambda used: self._report_add(
                      "密钥生成", "SEED 直注" if used else "PUF 挑战", "成功"))

    def _do_sign(self):
        if not self._need_be():
            return

        def fn(w):
            w.step.emit("sign")
            t0 = time.perf_counter()
            sig = self.backend.sign()
            ms = (time.perf_counter() - t0) * 1000.0
            if sig is None:
                raise RuntimeError("RES NOT READY（请先完成固件入库和密钥生成）")
            w.result.emit("sig", sig.hex())
            return ms
        self._run(fn, "Dilithium2 签名",
                  on_done=lambda ms: self._report_add(
                      "签名", "", f"成功，耗时 {ms:.0f} ms"))

    def _do_verify(self, sig=None, tamper=None):
        if not self._need_be():
            return
        if sig is None:
            text = self.ed_sig.toPlainText().strip()
            if not text:
                QMessageBox.information(self, "提示", "签名为空，请先生成签名")
                return
            try:
                sig = bytes.fromhex(text)
            except ValueError:
                QMessageBox.warning(self, "签名", "签名内容不是有效 hex")
                return

        def fn(w):
            w.step.emit("verify")
            t0 = time.perf_counter()
            ok = self.backend.ver(sig)
            ms = (time.perf_counter() - t0) * 1000.0
            if ok is None:
                raise RuntimeError("RES NOT READY")
            w.result.emit("verdict", (ok, ms, tamper))
            return dict(ok=ok, ms=ms, tamper=tamper)

        def done(r):
            self._report_add(
                "验签" + ("（篡改测试）" if r["tamper"] else ""),
                r["tamper"] or "",
                f"{'PASS' if r['ok'] else 'FAIL'}，耗时 {r['ms']:.0f} ms")
        self._run(fn, "Dilithium2 验签", on_done=done)

    def _tamper_sig(self):
        if not self._need_be() or not self.sig_wire:
            QMessageBox.information(self, "提示", "请先完成一次签名")
            return
        idx = random.randrange(len(self.sig_wire)) \
            if self.settings.get("tamper_random", True) else 50
        bad = bytearray(self.sig_wire)
        bad[idx] ^= 0xFF
        self._last_tamper = ("签名", idx)
        self._log("SYS", f"安全演示：签名第 {idx} 字节篡改，预期 FAIL")
        self._do_verify(bytes(bad), tamper=f"签名 字节 #{idx}")

    def _tamper_fw(self):
        if not self._need_be() or not self.sig_wire:
            QMessageBox.information(self, "提示", "请先完成一次签名")
            return
        original = self.fw_bytes
        idx = random.randrange(len(original)) \
            if self.settings.get("tamper_random", True) else 0
        bad = bytearray(original)
        bad[idx] ^= 1
        tamper = f"固件 字节 #{idx}"
        self._last_tamper = ("固件", idx)

        def fn(w):
            w.log.emit("SYS", f"安全演示：篡改固件第 {idx} 字节→签名→恢复原摘要→验签，预期 FAIL")
            w.step.emit("measure")
            digest = self.backend.fw(bytes(bad))
            w.result.emit("sha", digest.hex())
            w.step.emit("sign")
            sig = self.backend.sign()
            if sig is None:
                raise RuntimeError("RES NOT READY")
            w.result.emit("sig", sig.hex())
            w.step.emit("measure")
            digest0 = self.backend.fw(original)
            w.result.emit("sha", digest0.hex())
            w.step.emit("verify")
            t0 = time.perf_counter()
            ok = self.backend.ver(sig)
            ms = (time.perf_counter() - t0) * 1000.0
            w.result.emit("verdict", (ok, ms, tamper))
            return dict(ok=ok, ms=ms)

        def done(r):
            self._report_add("篡改固件并验证", tamper,
                             f"{'PASS' if r['ok'] else 'FAIL'}，耗时 {r['ms']:.0f} ms")
            self._log("SYS", "结果符合预期：FAIL" if r["ok"] is False
                      else "结果异常，请复核")
        self._run(fn, "篡改固件并验证", on_done=done)

    def _demo(self):
        if not self.backend:
            self._demo_after_connect = True
            self._connect()
            return
        self._log("SYS", f"一键演示开始，当前后端：{self._mode_desc()}")
        try:
            challenge = self._chal_bytes()
        except Exception as e:
            QMessageBox.warning(self, "输入有误", str(e))
            self._go_page(3)
            return
        firmware = self.fw_bytes
        use_seed = self._use_seed()

        def fn(w):
            w.step.emit("measure")
            digest = self.backend.fw(firmware)
            w.result.emit("sha", digest.hex())
            w.step.emit("puf")
            if use_seed:
                self.backend.seed(challenge)
                response_text = challenge.hex()
            else:
                response = self.backend.chal(challenge)
                response_text = response.hex() if response is not None else "N/A"
            w.result.emit("r", response_text)
            w.step.emit("keygen")
            pk = self.backend.pubk()
            sk = self.backend.priv()
            if pk:
                w.result.emit("pk", pk.hex())
            if sk:
                w.result.emit("sk", sk.hex())
            w.step.emit("sign")
            sig = self.backend.sign()
            if sig is None:
                raise RuntimeError("RES NOT READY")
            w.result.emit("sig", sig.hex())
            w.step.emit("verify")
            t0 = time.perf_counter()
            ok = self.backend.ver(sig)
            ms = (time.perf_counter() - t0) * 1000.0
            w.result.emit("verdict", (ok, ms, None))
            return dict(sha=digest.hex(), r=response_text,
                        pk=pk.hex() if pk else "N/A", ok=ok, ms=ms)

        def summary(result):
            self._go_page(4)
            if result:
                self._report_add(
                    "一键演示", "固件入库→密钥→签名→验签",
                    f"{'PASS' if result['ok'] else 'FAIL'}，验签 {result['ms']:.0f} ms")
            if self.fast or not result:
                return
            QMessageBox.information(
                self, "演示完成",
                f"固件 SHA3：{result['sha']}\n"
                f"公钥前缀：{result['pk'][:32]}…\n"
                f"验签结果：{'PASS' if result['ok'] else 'FAIL'}")
        self._run(fn, "一键演示全流程", on_done=summary)

    def _save_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存日志", "demo_log.txt")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.ed_log.toPlainText())

    def _export(self, box, name):
        text = box.toPlainText().strip()
        if not text:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出 " + name, name.lower() + ".hex")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text + "\n")

    def closeEvent(self, event):
        # 快速收尸：忙碌时直接 abort（杀进程树），空闲时才走优雅 QUIT，避免关窗卡顿
        be = self.backend
        self.backend = None
        if be is not None:
            try:
                if self._is_busy and hasattr(be, "abort"):
                    be.abort()
                else:
                    be.close()
            except Exception:
                pass
        proc = self._openocd_proc
        self._openocd_proc = None
        if proc is not None and proc.poll() is None:
            taskkill = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                                    "System32", "taskkill.exe")
            try:
                subprocess.run([taskkill, "/F", "/T", "/PID", str(proc.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=10)
            except Exception:
                pass
        super().closeEvent(event)


def main():
    fast = "--shot" in sys.argv

    def _excepthook(etype, value, tb):
        # PyQt 槽函数异常默认只打 stderr，界面上表现为"点了没反应"——落盘便于排查
        import traceback
        try:
            with open(os.path.join(BASE_DIR, "gui_error.log"), "a", encoding="utf-8") as f:
                f.write(f"\n[{ts()}] 未捕获异常（界面回调）:\n"
                        + "".join(traceback.format_exception(etype, value, tb)))
        except Exception:
            pass
        sys.__excepthook__(etype, value, tb)

    sys.excepthook = _excepthook
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    win = MainWindow(fast=fast, force_sim=fast)
    win.show()
    if fast:
        from PyQt5.QtCore import QTimer

        def shoot(*_):
            win.grab().save(os.path.join(BASE_DIR, "demo_screenshot.png"))
            app.quit()
        win._connect()
        QTimer.singleShot(300, win._demo)
        QTimer.singleShot(12000, shoot)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
