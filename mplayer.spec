# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller ビルド定義 (Windows 単体配布用)。

QtMultimedia の ffmpeg バックエンドは PySide6 同梱の av*/sw* DLL に依存するため、
これらを明示的に同梱する。multimedia プラグイン本体は PyInstaller の PySide6
フックが収集する。
"""
import os

import PySide6

_PYSIDE_DIR = os.path.dirname(os.path.abspath(PySide6.__file__))

# PySide6 直下の FFmpeg 依存 DLL (avcodec/avformat/avutil/swresample/swscale)
_FFMPEG_DLLS = [
    f for f in os.listdir(_PYSIDE_DIR)
    if f.endswith(".dll") and f.split("-")[0] in {
        "avcodec", "avformat", "avutil", "swresample", "swscale",
    }
]
binaries = [(os.path.join(_PYSIDE_DIR, d), ".") for d in _FFMPEG_DLLS]

# 未使用の重量級 Qt モジュールを除外してサイズを抑える
_EXCLUDES = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DAnimation",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtDesigner", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtSql",
    "PySide6.QtTest", "PySide6.QtBluetooth", "PySide6.QtNfc",
    "PySide6.QtPositioning", "PySide6.QtSerialPort", "PySide6.QtWebSockets",
    "PySide6.QtWebChannel", "PySide6.QtRemoteObjects", "PySide6.QtScxml",
    "PySide6.QtSensors", "PySide6.QtSpatialAudio", "PySide6.QtTextToSpeech",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtHelp",
    "tkinter", "unittest", "pydoc_data", "PyInstaller",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_EXCLUDES,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="mplayer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="mplayer",
)
