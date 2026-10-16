"""P8: 配布exe (PyInstaller) のスモークテスト。

dist/mplayer/mplayer.exe が無い場合は SKIP (通常のテスト実行を妨げない)。
exe の --selftest で実際にデコードが進むか検証する。
"""
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, skip

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(BASE, "dist", "mplayer", "mplayer.exe")
VIDEO = os.path.join(BASE, "test_640x360.mp4")


def main():
    if not os.path.isfile(EXE):
        skip("exe selftest", "dist exe not built (run build_exe.bat)")
        return finish("P8exe")

    out = os.path.join(tempfile.gettempdir(), "mplayer_p8_selftest.json")
    if os.path.isfile(out):
        os.remove(out)
    try:
        proc = subprocess.run(
            [EXE, "--selftest", VIDEO, "--selftest-out", out],
            timeout=90, capture_output=True,
        )
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        check("exe selftest terminates", False, "timeout")
        return finish("P8exe")

    check("exe selftest exit code 0", rc == 0, f"rc={rc}")
    result = {}
    try:
        with open(out, encoding="utf-8") as f:
            result = json.load(f)
    except Exception as e:
        check("exe wrote result", False, str(e))
    check("exe decoded video", bool(result.get("ok")), f"result={result}")
    check("exe advanced position", result.get("position", 0) > 0, f"result={result}")
    check("exe reported duration", result.get("duration", 0) > 0, f"result={result}")
    if os.path.isfile(out):
        os.remove(out)
    return finish("P8exe")


if __name__ == "__main__":
    sys.exit(main())
