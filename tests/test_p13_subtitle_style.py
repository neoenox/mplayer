"""P13: 字幕の表示設定 (サイズ/位置) と永続化の検証。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, patch_message_boxes, silence

from PySide6.QtWidgets import QMenu

import main as app_main
from main import PlayerWindow

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def label_index(w):
    for i in range(w._overlay.count()):
        if w._overlay.itemAt(i).widget() is w.subtitle_label:
            return i
    return -1


def main():
    patch_message_boxes()
    session = app_main.SESSION_FILE
    if os.path.isfile(session):
        os.remove(session)

    app = make_app()
    app.setQuitOnLastWindowClosed(False)

    w = PlayerWindow()
    w.show()
    silence(w)
    check("default size 18", w._sub_size == 18, f"{w._sub_size}")
    check("default pos bottom", w._sub_pos == "bottom", f"{w._sub_pos}")
    check("style has 18px", "18px" in w.subtitle_label.styleSheet())
    check("bottom: label is last", label_index(w) == w._overlay.count() - 1)

    w.set_subtitle_size(26)
    check("size set to 26", w._sub_size == 26)
    check("style has 26px", "26px" in w.subtitle_label.styleSheet())
    w.set_subtitle_size(999)
    check("size out of range ignored", w._sub_size == 26)

    w.set_subtitle_pos("top")
    check("pos top", w._sub_pos == "top")
    check("top: label is first", label_index(w) == 0, f"idx={label_index(w)}")
    w.set_subtitle_pos("middle")
    check("pos middle", w._sub_pos == "middle")
    check("middle: label centered", label_index(w) == 1
          and w._overlay.count() == 3, f"idx={label_index(w)} n={w._overlay.count()}")
    w.set_subtitle_pos("bottom")
    check("back to bottom", label_index(w) == w._overlay.count() - 1)
    w.set_subtitle_pos("sideways")
    check("invalid pos ignored", w._sub_pos == "bottom")

    # メニュー項目の存在
    menus = {m.title(): m for m in w.menuBar().findChildren(QMenu)}
    check("subtitle menu exists", "字幕" in menus, f"{list(menus)}")

    # 永続化
    w.set_subtitle_size(26)
    w.set_subtitle_pos("top")
    w.close()
    raw = json.load(open(session, encoding="utf-8"))
    check("saved subtitle_size", raw.get("subtitle_size") == 26, f"{raw.get('subtitle_size')}")
    check("saved subtitle_pos", raw.get("subtitle_pos") == "top", f"{raw.get('subtitle_pos')}")

    w2 = PlayerWindow()
    w2.show()
    w2.restore_session()
    check("restore size", w2._sub_size == 26, f"{w2._sub_size}")
    check("restore pos", w2._sub_pos == "top", f"{w2._sub_pos}")
    check("restore layout top", label_index(w2) == 0)
    silence(w2)
    w2.close()

    os.remove(session)
    return finish("P13substyle")


if __name__ == "__main__":
    sys.exit(main())
