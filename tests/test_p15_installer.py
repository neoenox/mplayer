"""P15: Windows インストーラ (Inno Setup) の静的検証 + 生成物の検証。

- .iss / ビルダーの静的検査は常に実行
- dist/installer/mplayer-setup-*.exe があれば内容も検証 (無ければ SKIP)
"""
import glob
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, skip

import main as app_main

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISS = os.path.join(BASE, "installer", "mplayer.iss")
BUILDER = os.path.join(BASE, "tools", "make_installer.py")


def main():
    check("iss exists", os.path.isfile(ISS), ISS)
    check("builder exists", os.path.isfile(BUILDER), BUILDER)

    raw = open(ISS, "rb").read()
    check("iss has UTF-8 BOM", raw[:3] == b"\xef\xbb\xbf",
          f"{raw[:3].hex()}")

    text = raw.decode("utf-8-sig")
    for token in ("[Setup]", "[Files]", "[Icons]", "[Run]", "[Languages]",
                  "AppId=", "AppVersion={#AppVersion}",
                  'Source: "{#RepoRoot}\\dist\\mplayer\\*"',
                  "SetupIconFile={#RepoRoot}\\assets\\app.ico",
                  "ArchitecturesAllowed=x64compatible",
                  "Japanese.isl", "desktopicon"):
        check(f"iss contains {token!r}", token in text)

    setups = sorted(glob.glob(os.path.join(BASE, "dist", "installer",
                                           "mplayer-setup-*.exe")))
    if not setups:
        skip("setup exe present", "(未ビルド: make_installer.py を実行)")
    else:
        setup = setups[-1]
        size = os.path.getsize(setup)
        check("setup size > 10MB", size > 10 * 1024 * 1024, f"{size} bytes")
        with open(setup, "rb") as f:
            magic = f.read(2)
        check("setup has MZ signature", magic == b"MZ", f"{magic!r}")

        name = os.path.basename(setup)
        expected = f"mplayer-setup-{app_main.__version__}.exe"
        check("setup filename matches version", name == expected,
              f"{name} (version {app_main.__version__})")

        import ctypes
        from ctypes import wintypes

        ver = ctypes.windll.version
        ver.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]
        ver.GetFileVersionInfoSizeW.restype = wintypes.DWORD
        ver.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                            wintypes.DWORD, ctypes.c_void_p]
        ver.GetFileVersionInfoW.restype = wintypes.BOOL
        ver.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR,
                                       ctypes.POINTER(ctypes.c_void_p),
                                       ctypes.POINTER(wintypes.UINT)]
        ver.VerQueryValueW.restype = wintypes.BOOL

        # バージョン情報は win32 API 経由で読む (PowerShell/GUI 不要)
        size_ptr = ver.GetFileVersionInfoSizeW(setup, None)
        check("setup has version resource", size_ptr > 0, f"{size_ptr}")
        if size_ptr > 0:
            buf = ctypes.create_string_buffer(size_ptr)
            assert ver.GetFileVersionInfoW(setup, 0, size_ptr, buf)
            tr = ctypes.c_void_p()
            length = wintypes.UINT()
            ok = ver.VerQueryValueW(buf, "\\VarFileInfo\\Translation",
                                    ctypes.byref(tr), ctypes.byref(length))
            check("version translation present", bool(ok) and length.value >= 4)
            if ok:
                cp = ctypes.cast(tr, ctypes.POINTER(wintypes.WORD))
                langid = f"{cp[0]:04x}{cp[1]:04x}"
                company = ""
                for key in ("CompanyName", "ProductName"):
                    ptr = ctypes.c_void_p()
                    ln = wintypes.UINT()
                    sub = f"\\StringFileInfo\\{langid}\\{key}"
                    if ver.VerQueryValueW(buf, sub, ctypes.byref(ptr),
                                          ctypes.byref(ln)) and ln.value:
                        val = ctypes.wstring_at(ptr, ln.value - 1).strip()
                        if key == "CompanyName":
                            company = val
                        else:
                            check("setup ProductName == APP_NAME",
                                  val == app_main.APP_NAME, f"{val!r}")
                check("setup CompanyName == mplayer", company == "mplayer",
                      f"{company!r}")

    return finish("P15installer")


if __name__ == "__main__":
    sys.exit(main())
