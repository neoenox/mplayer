# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller ビルド定義 (Windows 単体配布用)。

QtMultimedia の ffmpeg バックエンドは PySide6 同梱の av*/sw* DLL に依存するため、
これらを明示的に同梱する。multimedia プラグイン本体は PyInstaller の PySide6
フックが収集する。
"""
import os
import re
import tempfile

import PySide6

_ROOT = os.path.abspath(globals().get("SPECPATH", os.getcwd()))
_PYSIDE_DIR = os.path.dirname(os.path.abspath(PySide6.__file__))

# main.py の __version__ を唯一の情報源として exe のバージョン情報を生成する
with open(os.path.join(_ROOT, "main.py"), encoding="utf-8") as _f:
    _VER = re.search(r'__version__\s*=\s*"([^"]+)"', _f.read()).group(1)
_VER4 = ".".join((_VER.split(".") + ["0", "0", "0", "0"])[:4])
_VERSION_FILE = os.path.join(tempfile.gettempdir(), f"mplayer_version_{_VER}.txt")
with open(_VERSION_FILE, "w", encoding="utf-8") as _f:
    _f.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({_VER4.replace('.', ', ')}),
    prodvers=({_VER4.replace('.', ', ')}),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'mplayer'),
        StringStruct('FileDescription', 'シンプル動画プレイヤー'),
        StringStruct('FileVersion', '{_VER}'),
        StringStruct('OriginalFilename', 'mplayer.exe'),
        StringStruct('ProductName', 'シンプル動画プレイヤー'),
        StringStruct('ProductVersion', '{_VER}'),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""")

# 同梱リソース (アイコン)
_DATAS = [(os.path.join(_ROOT, "assets", "app.ico"), "assets")]
_ICON = os.path.join(_ROOT, "assets", "app.ico")

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
    datas=_DATAS,
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
    icon=_ICON,
    version=_VERSION_FILE,
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
