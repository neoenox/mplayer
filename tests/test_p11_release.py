"""P11: リリース準備 (バージョン表記・CHANGELOG・CIリリース設定) の検証。"""
import os
import re
import sys
import io
import json
import shutil
import tempfile
import zipfile

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
    check("updater disabled in tests", updater.enabled() is False)
    check("version comparison", updater.version_tuple("v1.27.0") == (1, 27, 0)
          and updater.is_newer("v1.29.0", app_main.__version__))
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
    release = {
        "tag_name": "v9.9.9",
        "assets": [{"name": "mplayer-windows-v9.9.9.zip",
                    "browser_download_url": "https://example.invalid/app.zip"}],
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
        return FakeResponse(payload)

    stage = updater.prepare(tmpdir, app_main.__version__, fake_opener)
    check("updater stages newer portable zip",
          bool(stage) and os.path.isfile(os.path.join(stage, "mplayer.exe")),
          str(stage))
    if stage:
        shutil.rmtree(stage, ignore_errors=True)
    shutil.rmtree(tmpdir, ignore_errors=True)

    make_app()
    w = app_main.PlayerWindow()
    check("title has version", app_main.__version__ in w.windowTitle(),
          f"title={w.windowTitle()!r}")
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

    return finish("P11release")


if __name__ == "__main__":
    sys.exit(main())
