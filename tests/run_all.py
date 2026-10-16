"""P3: テストランナー。各ステージを別プロセス+タイムアウトで実行し集計・保存する。

- 件数表示の不整合対策: [PASS]/[FAIL]/[SKIP] 行をパースして自動集計
- フリーズ対策: タイムアウトでkillし TIMEOUT として記録、後続継続
- ログ: test_logs/<stage>.log + test_logs/summary.txt、環境情報も記録
"""
import os
import re
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 使用venvは切替可能 (P4クリーン検証用 / CI)。MPLAYER_PYTHON > --python > 既定.venv。
# .venv が無い環境 (CI等) では現行インタプリタにフォールバックする。
_DEFAULT_PY = os.path.join(BASE, ".venv", "Scripts", "python.exe")
VENV_PY = os.environ.get("MPLAYER_PYTHON") or _DEFAULT_PY
if not os.path.exists(VENV_PY):
    VENV_PY = sys.executable
LOGDIR = os.path.join(BASE, "test_logs")

STAGES = [
    ("p6_controls", "tests/test_p6_controls.py", 60),
    ("p0_decode", "tests/test_p0_decode.py", 150),
    ("p1a_open_play", "tests/test_p1a_open_play.py", 100),
    ("p1b_seek", "tests/test_p1b_seek.py", 100),
    ("p1c_audio_fs", "tests/test_p1c_audio_fs.py", 100),
    ("p1d_dnd_misc", "tests/test_p1d_dnd_misc.py", 120),
    ("p2_robustness", "tests/test_p2_robustness.py", 180),
    ("p4_extra", "tests/test_p4_extra.py", 150),
    ("p5_race", "tests/test_p5_seek_race.py", 150),
    ("p5_endurance", "tests/test_p5_endurance.py", 300),
    ("p6_features", "tests/test_p6_features.py", 150),
    ("p7_resume", "tests/test_p7_resume.py", 150),
    ("p8_exe", "tests/test_p8_exe.py", 150),
    ("p9_subtitle", "tests/test_p9_subtitle.py", 150),
    ("p10_playlist", "tests/test_p10_playlist.py", 180),
    ("p11_release", "tests/test_p11_release.py", 60),
    ("p12_settings", "tests/test_p12_settings.py", 90),
    ("p13_subtitle_style", "tests/test_p13_subtitle_style.py", 90),
    ("p14_icon", "tests/test_p14_icon.py", 60),
    ("p15_installer", "tests/test_p15_installer.py", 60),
    ("p16_subtitle_enc", "tests/test_p16_subtitle_enc.py", 90),
    ("p17_help", "tests/test_p17_help.py", 60),
    ("p18_dnd_folder", "tests/test_p18_dnd_folder.py", 90),
    ("p19_stability", "tests/test_p19_stability.py", 300),
    ("p20_speed", "tests/test_p20_speed.py", 90),
]


def _pyside_dir():
    """使用インタプリタの PySide6 ディレクトリを解決する (venv/CI両対応)。"""
    for py in (VENV_PY, sys.executable):
        try:
            out = subprocess.run(
                [py, "-c", "import PySide6,os;print(os.path.dirname(PySide6.__file__))"],
                capture_output=True, text=True, timeout=30)
            d = (out.stdout or "").strip()
            if d and os.path.isdir(d):
                return d
        except Exception:
            pass
    # フォールバック: .venv レイアウトを仮定
    return os.path.normpath(os.path.join(os.path.dirname(VENV_PY), "..", "Lib",
                                         "site-packages", "PySide6"))


def env_info():
    lines = []
    try:
        v = subprocess.run([VENV_PY, "--version"], capture_output=True, text=True, timeout=30)
        lines.append("python: " + (v.stdout or v.stderr).strip())
    except Exception as e:
        lines.append(f"python: <err {e}>")
    try:
        v = subprocess.run([VENV_PY, "-m", "pip", "freeze"], capture_output=True, text=True, timeout=60)
        for ln in v.stdout.splitlines():
            if "PySide" in ln or "shiboken" in ln:
                lines.append("pip: " + ln)
    except Exception as e:
        lines.append(f"pip: <err {e}>")
    pyside = _pyside_dir()
    plug = os.path.join(pyside, "plugins", "multimedia")
    try:
        for f in sorted(os.listdir(plug)):
            lines.append(f"plugin: {f} {os.path.getsize(os.path.join(plug, f))}B")
    except Exception as e:
        lines.append(f"plugin: <err {e}>")
    for dll in ("avcodec-63.dll", "avformat-63.dll", "avutil-61.dll"):
        p = os.path.join(pyside, dll)
        lines.append(f"dll: {dll} {'%dB' % os.path.getsize(p) if os.path.exists(p) else 'MISSING'}")
    return "\n".join(lines)


def main():
    import argparse
    # 子プロセスは UTF-8 で出力する (PYTHONUTF8=1)。コンソール既定 (cp932) で
    # 日本語や置換文字を print すると落ちるため、標準出力を UTF-8 に切り替える。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="mplayer test runner (quiet by default)")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="子プロセスの出力をそのまま流す (うるさい)")
    ap.add_argument("--python", default=None, help="使用するPython (既定: MPLAYER_PYTHONか.venv)")
    ap.add_argument("stages", nargs="*", help="実行するステージ名 (省略時は全部)")
    args = ap.parse_args()
    global VENV_PY
    if args.python:
        if os.path.exists(args.python):
            VENV_PY = args.python
        else:
            print(f"warn: --python not found ({args.python}); using {sys.executable}", flush=True)

    os.makedirs(LOGDIR, exist_ok=True)
    total_p = total_f = total_s = 0
    rows = []
    wanted = set(args.stages)
    for name, rel, timeout in STAGES:
        if wanted and name not in wanted and rel not in wanted:
            continue
        print(f"--- {name} ...", flush=True, end="" if not args.verbose else "\n")
        env = dict(os.environ, MPLAYER_DUMP_SECS="30",
                   MPLAYER_DUMP_FILE=os.path.join(LOGDIR, f"{name}.pydump.txt"),
                   MPLAYER_SESSION_FILE=os.path.join(LOGDIR, f"{name}.session.json"),
                   PYTHONUTF8="1",
                   QT_LOGGING_RULES="*.debug=false;qt.multimedia.*.info=false")
        try:
            os.remove(env["MPLAYER_SESSION_FILE"])
        except OSError:
            pass
        try:
            cp = subprocess.run([VENV_PY, "-u", rel], cwd=BASE, capture_output=True,
                                text=True, timeout=timeout, errors="replace",
                                encoding="utf-8", env=env)
            out = (cp.stdout or "") + "\n[stderr]\n" + (cp.stderr or "")
            status = "EXIT" if cp.returncode == 0 else "EXIT-NONZERO"
            code = cp.returncode
        except subprocess.TimeoutExpired as e:
            out = ((e.stdout or "") if isinstance(e.stdout, str) else "") + \
                f"\n[TIMEOUT after {timeout}s: freeze suspected, killed]\n"
            status, code = "TIMEOUT", "timeout"
        with open(os.path.join(LOGDIR, f"{name}.log"), "w", encoding="utf-8") as f:
            f.write(out)
        if args.verbose:
            print(f"\n===== {name} log =====", flush=True)
            print(out[-6000:], flush=True)
            print(f"===== end {name} =====", flush=True)
        p = len(re.findall(r"\[PASS\]", out))
        fl = len(re.findall(r"\[FAIL\]", out))
        sk = len(re.findall(r"\[SKIP\]", out))
        m = re.search(r"== .* RESULT: (\d+) passed, (\d+) failed", out)
        if m:
            p, fl = int(m.group(1)), int(m.group(2))
        total_p += p
        total_f += fl
        total_s += sk
        ok = status == "EXIT" and code == 0 and fl == 0
        rows.append((name, "PASS" if ok else ("FAIL" if fl else status), p, fl, sk))
        print(f"\r{name}: {rows[-1][1]} (pass={p} fail={fl} skip={sk})", flush=True)

    summary = ["# mplayer test summary", "", "## env", env_info(), "", "## stages"]
    for name, res, p, fl, sk in rows:
        summary.append(f"- {name}: {res} (pass={p} fail={fl} skip={sk})")
    summary.append(f"\nTOTAL: {total_p} passed, {total_f} failed, {total_s} skipped")
    text = "\n".join(summary)
    with open(os.path.join(LOGDIR, "summary.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    # コンソールは1行サマリーのみ。詳細は test_logs/ を見る。
    for name, res, p, fl, sk in rows:
        print(f"  {name}: {res} ({p}/{p + fl + sk})", flush=True)
    print(f"TOTAL: {total_p} passed, {total_f} failed, {total_s} skipped"
          f"  (logs: test_logs/)", flush=True)
    return 1 if total_f or any(r[1] not in ("PASS",) for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
