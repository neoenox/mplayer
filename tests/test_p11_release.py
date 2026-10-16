"""P11: リリース準備 (バージョン表記・CHANGELOG・CIリリース設定) の検証。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, patch_message_boxes

import main as app_main

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    patch_message_boxes()
    check("version constant is 1.0.0", app_main.__version__ == "1.0.0",
          f"ver={app_main.__version__}")
    check("app name set", bool(app_main.APP_NAME))

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
