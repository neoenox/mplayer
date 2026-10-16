"""Inno Setup で Windows インストーラをビルドする。

前提: dist/mplayer/ に exe 一式がビルド済み (build_exe.bat 参照)。

使い方:
    .venv\\Scripts\\python.exe tools\\make_installer.py

ISCC.exe は次の順で探索する:
    1. 環境変数 INNO_SETUP (ISCC.exe へのパス)
    2. %LOCALAPPDATA%\\Programs\\Inno Setup 6\\ISCC.exe
    3. %ProgramFiles%\\Inno Setup 6\\ISCC.exe
    4. %ProgramFiles(x86)%\\Inno Setup 6\\ISCC.exe
    5. PATH 上の iscc
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISS = os.path.join(ROOT, "installer", "mplayer.iss")
DIST_APP = os.path.join(ROOT, "dist", "mplayer")
OUT_DIR = os.path.join(ROOT, "dist", "installer")


def read_version() -> str:
    with open(os.path.join(ROOT, "main.py"), encoding="utf-8") as f:
        return re.search(r'__version__\s*=\s*"([^"]+)"', f.read()).group(1)


def find_iscc() -> str | None:
    env = os.environ.get("INNO_SETUP")
    if env and os.path.isfile(env):
        return env
    candidates = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Inno Setup 6", "ISCC.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Inno Setup 6", "ISCC.exe"),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return shutil.which("iscc")


def main() -> int:
    if not os.path.isfile(os.path.join(DIST_APP, "mplayer.exe")):
        print(f"error: {DIST_APP} に exe がありません。先に exe をビルドしてください。",
              file=sys.stderr)
        return 2

    iscc = find_iscc()
    if not iscc:
        print("error: ISCC.exe (Inno Setup 6) が見つかりません。INNO_SETUP で指定できます。",
              file=sys.stderr)
        return 3

    version = read_version()
    os.makedirs(OUT_DIR, exist_ok=True)
    out_name = f"mplayer-setup-{version}.exe"
    out_path = os.path.join(OUT_DIR, out_name)

    cmd = [iscc, f"/DAppVersion={version}", f"/DRepoRoot={ROOT}", ISS]
    print(f"$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    tail = "\n".join((proc.stdout or "").splitlines()[-6:])
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        print(f"error: ISCC failed (rc={proc.returncode})", file=sys.stderr)
        return proc.returncode
    print(tail)
    if not os.path.isfile(out_path):
        print(f"error: 出力がありません: {out_path}", file=sys.stderr)
        return 4
    print(f"OK: {out_path} ({os.path.getsize(out_path)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
