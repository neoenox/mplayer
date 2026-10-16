"""P14: アプリアイコン (assets/app.ico) の存在・妥当性・適用の検証。"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, patch_message_boxes

from PySide6.QtGui import QIcon

import main as app_main
from main import PlayerWindow

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICO = os.path.join(BASE, "assets", "app.ico")


def main():
    patch_message_boxes()
    check("icon file exists", os.path.isfile(ICO), ICO)
    size = os.path.getsize(ICO) if os.path.isfile(ICO) else 0
    check("icon has sane size", size > 1000, f"{size} bytes")

    with open(ICO, "rb") as f:
        head = f.read(6)
    reserved, itype, count = struct.unpack("<HHH", head)
    check("ico header reserved=0", reserved == 0)
    check("ico header type=1 (icon)", itype == 1)
    check("ico has 6 sizes", count == 6, f"count={count}")

    check("resource path points to icon", app_main.ICON_PATH == ICO,
          f"{app_main.ICON_PATH}")

    make_app()
    ic = QIcon(ICO)
    check("QIcon not null", not ic.isNull())
    sizes = {(s.width(), s.height()) for s in ic.availableSizes()}
    check("icon has 256 px", (256, 256) in sizes, f"{sorted(sizes)}")
    check("icon has 32 px", (32, 32) in sizes)
    check("icon has 16 px", (16, 16) in sizes)

    w = PlayerWindow()
    check("window icon set", not w.windowIcon().isNull())
    w.close()
    return finish("P14icon")


if __name__ == "__main__":
    sys.exit(main())
