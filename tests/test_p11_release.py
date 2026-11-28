"""P11: リリース準備 (バージョン表記・CHANGELOG・CIリリース設定) の検証。"""
import os
import hashlib
import re
import sys
import io
import json
import shutil
import tempfile
import zipfile
import subprocess
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, patch_message_boxes

import main as app_main
import updater

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    patch_message_boxes()
    check("version is semver", bool(re.fullmatch(r"\d+\.\d+\.\d+", app_main.__version__)),
          f"ver={app_main.__version__}")
    check("app name set", bool(app_main.APP_NAME))
    check("state dir is user-local",
          os.path.basename(app_main.STATE_DIR) == "mplayer")
    check("extension filter has single authority",
          app_main.SUPPORTED_FILTER
          == "動画ファイル (*" + " *".join(app_main.VIDEO_EXTS) + ");;すべてのファイル (*.*)")
    check("outline width normalized",
          abs(app_main.subtitle_outline_width(18) - 2.7) < 1e-9
          and app_main.subtitle_outline_width(4) == 1.5)
    check("updater uses shared atomic writer",
          updater.atomic_write_json is app_main.atomic_write_json)
    check("dead updater helpers removed",
          not hasattr(updater, "take_pending")
          and not hasattr(updater, "PRESERVE_FILES"))
    check("updater disabled in tests", updater.enabled() is False)
    old_no_update = os.environ.pop("MPLAYER_NO_AUTOUPDATE", None)
    old_auto = os.environ.get("MPLAYER_AUTOUPDATE")
    os.environ["MPLAYER_AUTOUPDATE"] = "1"
    old_fetch = updater.fetch_latest

    def boom(*args, **kwargs):
        raise RuntimeError("offline")

    updater.fetch_latest = boom
    try:
        updater.start_background_check(tempfile.mkdtemp(), app_main.__version__)
        for _ in range(20):
            if updater.status().get("text") == "":
                break
            time.sleep(0.05)
        check("check failure is silent", updater.status().get("text") == "",
              str(updater.status()))
    finally:
        updater.fetch_latest = old_fetch
        if old_no_update is not None:
            os.environ["MPLAYER_NO_AUTOUPDATE"] = old_no_update
        if old_auto is None:
            os.environ.pop("MPLAYER_AUTOUPDATE", None)
        else:
            os.environ["MPLAYER_AUTOUPDATE"] = old_auto
    major, minor, patch = updater.version_tuple(app_main.__version__)[:3]
    newer = f"v{major}.{minor}.{patch + 1}"
    check("version comparison", updater.version_tuple("v1.27.0") == (1, 27, 0)
          and updater.is_newer(newer, app_main.__version__))
    check("portable asset detection", updater.find_portable_asset({"assets": [
        {"name": "mplayer-setup-1.28.0.exe", "browser_download_url": "https://x/setup.exe"},
        {"name": "mplayer-windows-v1.28.0.zip", "browser_download_url": "https://x/app.zip"},
    ]}) == ("https://x/app.zip", "mplayer-windows-v1.28.0.zip"))
    # ネットワークを使わずに「新版本をステージするところまで」を検証する。
    tmpdir = tempfile.mkdtemp()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("mplayer.exe", b"dummy")
    payload = buf.getvalue()
    expected_sha = hashlib.sha256(payload).hexdigest()
    release = {
        "tag_name": "v9.9.9",
        "assets": [
            {"name": "mplayer-windows-v9.9.9.zip",
             "browser_download_url": "https://example.invalid/app.zip"},
            {"name": "mplayer-windows-v9.9.9.zip.sha256",
             "browser_download_url": "https://example.invalid/app.zip.sha256"},
        ],
    }

    class FakeResponse:
        def __init__(self, data):
            self._data = data
            self._pos = 0

        def read(self, size=-1):
            if self._pos >= len(self._data):
                return b""
            end = len(self._data) if size < 0 else self._pos + size
            chunk = self._data[self._pos:end]
            self._pos = end
            return chunk

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_opener(request, timeout=None):
        if "releases/latest" in request.full_url:
            return FakeResponse(json.dumps(release).encode("utf-8"))
        if request.full_url.endswith(".sha256"):
            return FakeResponse(expected_sha.encode("ascii"))
        return FakeResponse(payload)

    stage = updater.prepare(tmpdir, app_main.__version__, fake_opener)
    check("updater stages newer portable zip",
          bool(stage) and os.path.isfile(os.path.join(stage, "mplayer.exe")),
          str(stage))
    if stage:
        shutil.rmtree(stage, ignore_errors=True)
    shutil.rmtree(tmpdir, ignore_errors=True)
    bad_release = {
        "tag_name": "v9.9.9",
        "assets": [
            {"name": "mplayer-windows-v9.9.9.zip",
             "browser_download_url": "https://example.invalid/app.zip"},
            {"name": "mplayer-windows-v9.9.9.zip.sha256",
             "browser_download_url": "https://example.invalid/app.zip.sha256"},
        ],
    }

    def bad_opener(request, timeout=None):
        if "releases/latest" in request.full_url:
            return FakeResponse(json.dumps(bad_release).encode("utf-8"))
        if request.full_url.endswith(".sha256"):
            return FakeResponse(("0" * 64).encode("ascii"))
        return FakeResponse(payload)

    bad_dir = tempfile.mkdtemp()
    check("checksum mismatch rejects update",
          updater.prepare(bad_dir, app_main.__version__, bad_opener) is None)
    shutil.rmtree(bad_dir, ignore_errors=True)
    # 終了後適用ヘルパーが実際に動くか (短命プロセスのPIDで終了を模擬)。
    apply_base = tempfile.mkdtemp(prefix="mplayer-apply-")
    apply_app = os.path.join(apply_base, "mplayer")
    apply_stage = os.path.join(apply_base, "mplayer-update")
    os.makedirs(apply_app)
    os.makedirs(apply_stage)
    dummy = r"C:\Windows\System32\where.exe"
    shutil.copy(dummy, os.path.join(apply_app, "mplayer.exe"))
    shutil.copy(dummy, os.path.join(apply_stage, "mplayer.exe"))
    with open(os.path.join(apply_app, "resume.json"), "w", encoding="utf-8") as f:
        f.write("{}")
    with open(os.path.join(apply_stage, "applied-marker.txt"), "w", encoding="utf-8") as f:
        f.write("ok")
    short = subprocess.Popen([sys.executable, "-c", "pass"])
    short.wait()
    result_path = os.path.join(apply_base, "update_result.json")
    updater.start_apply(apply_app, apply_stage, pid=short.pid, exe_name="mplayer.exe",
                        marker_path=result_path, from_version="1.28.1",
                        to_version="v1.29.0")
    marker = os.path.join(apply_app, "applied-marker.txt")
    applied = False
    for _ in range(80):
        if os.path.isfile(marker):
            applied = True
            break
        time.sleep(0.25)
    check("updater applies staged package", applied)
    check("updater preserves resume.json",
          os.path.isfile(os.path.join(apply_app, "resume.json")))
    result_data = None
    for _ in range(80):
        if os.path.isfile(result_path):
            try:
                with open(result_path, encoding="utf-8-sig") as f:
                    result_data = json.load(f)
                break
            except Exception:
                pass
        time.sleep(0.25)
    check("update result marker written", bool(result_data and result_data.get("ok")),
          str(result_data))
    check("update marker has versions",
          bool(result_data and result_data.get("from") == "1.28.1"
               and result_data.get("to") == "v1.29.0"), str(result_data))
    check("apply helper retries rename",
          "Rename-WithRetry" in updater._POWERSHELL
          and "Start-Sleep -Milliseconds 1500" in updater._POWERSHELL)
    shutil.rmtree(apply_base, ignore_errors=True)
    legacy_dir = tempfile.mkdtemp()
    fresh_dir = tempfile.mkdtemp()
    with open(os.path.join(legacy_dir, "resume.json"), "w", encoding="utf-8") as f:
        json.dump({"legacy": True}, f)
    old_legacy = app_main.LEGACY_STATE_DIR
    try:
        app_main.LEGACY_STATE_DIR = legacy_dir
        check("legacy state migrated",
              app_main.load_state_json(os.path.join(fresh_dir, "resume.json"),
                                       "resume.json", False) == {"legacy": True})
        check("explicit state path skips legacy",
              app_main.load_state_json(os.path.join(fresh_dir, "resume.json"),
                                       "resume.json", True) == {})
    finally:
        app_main.LEGACY_STATE_DIR = old_legacy
    shutil.rmtree(legacy_dir, ignore_errors=True)
    shutil.rmtree(fresh_dir, ignore_errors=True)
    state_tmp = tempfile.mkdtemp()
    old_state_env = os.environ.get("MPLAYER_STATE_DIR")
    os.environ["MPLAYER_STATE_DIR"] = state_tmp
    try:
        updater.record_update_result(False, "1.28.1", "v1.29.0", "boom")
        failure = updater.consume_update_result()
        check("failure marker round-trip",
              bool(failure and failure.get("ok") is False
                   and failure.get("reason") == "boom"), str(failure))
        check("marker consumed once", updater.consume_update_result() is None)
        stale_path = updater.update_result_path()
        with open(stale_path, "w", encoding="utf-8") as f:
            json.dump({"ok": False, "reason": "old",
                       "time": "2020-01-01T00:00:00"}, f)
        check("stale failure marker ignored", updater.consume_update_result() is None)
    finally:
        if old_state_env is None:
            os.environ.pop("MPLAYER_STATE_DIR", None)
        else:
            os.environ["MPLAYER_STATE_DIR"] = old_state_env
    shutil.rmtree(state_tmp, ignore_errors=True)
    make_app()
    w = app_main.PlayerWindow()
    check("title has version", app_main.__version__ in w.windowTitle(),
          f"title={w.windowTitle()!r}")
    check("empty state has open button", not w.empty_open_btn.isHidden())
    check("manual update check action",
          w.check_update_act.objectName() == "check_update")
    check("update toast hidden initially", w.update_toast.isHidden())
    updater.set_status("更新あり · 終了時に適用します", staged=True)
    w.refresh_update_label()
    check("update toast shows update",
          not w.update_toast.isHidden() and "更新あり" in w.toast_label.text()
          and w.toast_icon.text() == "↓")
    updater.clear_status()
    w.refresh_update_label()
    check("update toast hides when cleared", w.update_toast.isHidden())
    w.show_update_result({"ok": True, "from": "1.28.1", "to": "v1.29.0"})
    w.refresh_update_label()
    check("completion toast shown",
          not w.update_toast.isHidden() and "更新完了" in w.toast_label.text()
          and w.toast_icon.text() == "✓",
          w.toast_label.text())
    check("completion toast styled green", "#7ee787" in w.toast_label.styleSheet(),
          w.toast_label.styleSheet())
    w.show_update_result({"ok": False, "reason": "boom"})
    w.refresh_update_label()
    check("failure toast shown", "更新に失敗" in w.toast_label.text()
          and w.toast_icon.text() == "!", w.toast_label.text())
    check("failure toast styled red", "#ff7b72" in w.toast_label.styleSheet(),
          w.toast_label.styleSheet())
    updater.clear_status()
    w.refresh_update_label()
    w.close()

    cl = os.path.join(BASE, "CHANGELOG.md")
    check("CHANGELOG exists", os.path.isfile(cl))
    if os.path.isfile(cl):
        text = open(cl, encoding="utf-8").read()
        check("CHANGELOG documents version", f"[{app_main.__version__}]" in text,
              "missing version header")

    ci = os.path.join(BASE, ".github", "workflows", "ci.yml")
    check("ci workflow exists", os.path.isfile(ci))
    if os.path.isfile(ci):
        ctext = open(ci, encoding="utf-8").read()
        check("ci creates release on tags",
              "softprops/action-gh-release" in ctext and "contents: write" in ctext)
        check("ci signs tagged binaries",
              "CODE_SIGN_PFX" in ctext and "signtool" in ctext)

    return finish("P11release")


if __name__ == "__main__":
    sys.exit(main())
