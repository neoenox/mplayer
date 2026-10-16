"""アプリアイコン (assets/app.ico) を生成する。

青い角丸背景に白い再生三角を描き、複数サイズの PNG を ICO コンテナに
詰めて出力する (Vista 以降は PNG 埋め込み ICO をサポート)。

使い方:
    .venv\Scripts\python.exe tools\make_icon.py
"""
from __future__ import annotations

import os
import struct
import sys

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QGuiApplication, QImage, QLinearGradient,
                           QPainter, QPainterPath)
from PySide6.QtWidgets import QApplication

SIZES = [256, 128, 64, 48, 32, 16]
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "assets", "app.ico")
PNG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "assets")


def render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    r = size * 0.18
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0.0, QColor("#4f9cf9"))
    grad.setColorAt(1.0, QColor("#1e3a8a"))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(0, 0, size, size), r, r)

    p.setBrush(QColor("white"))
    path = QPainterPath()
    left = size * 0.34
    right = size * 0.70
    top = size * 0.28
    bottom = size * 0.72
    path.moveTo(left, top)
    path.lineTo(right, size * 0.5)
    path.lineTo(left, bottom)
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return img


def png_bytes(img: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(ba)


def build_ico(path: str) -> None:
    images = [png_bytes(render(s)) for s in SIZES]
    n = len(SIZES)
    header = struct.pack("<HHH", 0, 1, n)
    offset = 6 + 16 * n
    entries = b""
    for size, data in zip(SIZES, images):
        w = 0 if size >= 256 else size
        h = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    with open(path, "wb") as f:
        f.write(header + entries + b"".join(images))


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    _ = app  # QGuiApplication が必要 (QImage 描画のため)
    os.makedirs(PNG_DIR, exist_ok=True)
    build_ico(OUT)
    print(f"wrote {OUT} ({os.path.getsize(OUT)} bytes, sizes={SIZES})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
