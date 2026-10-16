"""P21: 字幕の文字色・フォント選択 (縁取りの自動反転 / セッション保存)。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, patch_message_boxes, silence

from PySide6.QtGui import QColor, QImage

from main import (SUB_COLORS, SUB_FONTS, PlayerWindow, SubtitleLabel,
                  contrast_outline)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO = os.path.join(BASE, "test_640x360.mp4")
RESUME = os.path.join(BASE, "resume.json")


def colors_of(pairs):
    return [c for _, c in pairs]


def main():
    patch_message_boxes()
    make_app()

    check("配色は6種", len(SUB_COLORS) == 6, f"{len(SUB_COLORS)}")
    check("配色は一意", len(set(colors_of(SUB_COLORS))) == len(SUB_COLORS))
    check("既定の白がある", (255, 255, 255) in colors_of(SUB_COLORS))
    check("フォントは5種 (既定含む)", len(SUB_FONTS) == 5, f"{len(SUB_FONTS)}")
    check("フォント既定は空文字", SUB_FONTS[0] == ("既定", ""))
    check("フォントは一意", len({f for _, f in SUB_FONTS}) == len(SUB_FONTS))

    check("縁取り: 白→黒", contrast_outline((255, 255, 255)) == (0, 0, 0))
    check("縁取り: 黒→白", contrast_outline((0, 0, 0)) == (255, 255, 255))
    check("縁取り: 黄→黒", contrast_outline((255, 235, 59)) == (0, 0, 0))
    check("縁取り: 水色→黒", contrast_outline((79, 195, 247)) == (0, 0, 0))

    lbl = SubtitleLabel()
    check("既定の塗りは白", lbl.fill_color() == QColor(255, 255, 255),
          str(lbl.fill_color().name()))
    check("既定の縁取りは黒", lbl.outline_color() == QColor(0, 0, 0))
    lbl.set_fill_color((0, 0, 0))
    check("黒指定で塗りが黒", lbl.fill_color() == QColor(0, 0, 0))
    check("黒指定で縁取りが白へ自動反転",
          lbl.outline_color() == QColor(255, 255, 255),
          str(lbl.outline_color().name()))
    lbl.set_fill_color((255, 235, 59))
    check("黄指定で縁取りは黒のまま", lbl.outline_color() == QColor(0, 0, 0))
    lbl.set_font_family("Meiryo")
    check("フォント保持", lbl.font_family() == "Meiryo")
    lbl.set_font_family("")
    check("フォント解除で空", lbl.font_family() == "")

    w = PlayerWindow()
    silence(w)
    w._resume = {}
    check("窓の既定色は白", w._sub_color == (255, 255, 255), str(w._sub_color))
    check("窓の既定フォントは既定", w._sub_font == "", str(w._sub_font))
    check("文字色メニューは6件", len(w._sub_color_group.actions()) == 6)
    check("フォントメニューは5件", len(w._sub_font_group.actions()) == 5)
    check("文字色は1つだけ選択",
          sum(a.isChecked() for a in w._sub_color_group.actions()) == 1)
    check("フォントは1つだけ選択",
          sum(a.isChecked() for a in w._sub_font_group.actions()) == 1)

    w.set_subtitle_color((255, 235, 59))
    check("色設定が窓に反映", w._sub_color == (255, 235, 59), str(w._sub_color))
    check("色設定がラベルに反映",
          w.subtitle_label.fill_color() == QColor(255, 235, 59),
          str(w.subtitle_label.fill_color().name()))
    checked = [a.text() for a in w._sub_color_group.actions() if a.isChecked()]
    check("メニューのチェックが移動", checked == ["黄"], f"{checked}")

    w.set_subtitle_color((1, 2, 3))  # 未定義色は無視
    check("未定義色は無視", w._sub_color == (255, 235, 59), str(w._sub_color))
    w.set_subtitle_color("x")  # 型不正も無視
    check("型不正は無視", w._sub_color == (255, 235, 59))

    w.set_subtitle_font("Meiryo")
    check("フォント設定が窓に反映", w._sub_font == "Meiryo", w._sub_font)
    check("フォント設定がラベルに反映",
          w.subtitle_label.font_family() == "Meiryo")
    check("QSS に font-family が入る",
          "Meiryo" in w.subtitle_label.styleSheet(),
          w.subtitle_label.styleSheet())
    w.set_subtitle_font("存在しないフォント")
    check("未定義フォントは無視", w._sub_font == "Meiryo", w._sub_font)
    w.set_subtitle_font("")
    check("フォントを既定へ戻せる", w._sub_font == "")
    check("QSS から font-family が消える",
          "font-family" not in w.subtitle_label.styleSheet(),
          w.subtitle_label.styleSheet())

    # セッション往復
    w.set_subtitle_color((79, 195, 247))
    w.set_subtitle_font("MS Gothic")
    w._save_session()
    path = os.environ.get("MPLAYER_SESSION_FILE") or os.path.join(BASE, "session.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    check("保存: 色が入る", data.get("subtitle_color") == [79, 195, 247],
          str(data.get("subtitle_color")))
    check("保存: フォントが入る", data.get("subtitle_font") == "MS Gothic",
          str(data.get("subtitle_font")))

    w2 = PlayerWindow()
    silence(w2)
    w2._apply_session(data)
    check("復元: 色", w2._sub_color == (79, 195, 247), str(w2._sub_color))
    check("復元: フォント", w2._sub_font == "MS Gothic", str(w2._sub_font))
    check("復元: ラベルにも反映",
          w2.subtitle_label.fill_color() == QColor(79, 195, 247)
          and w2.subtitle_label.font_family() == "MS Gothic")

    # 壊れた値は無視して既定を保つ
    w3 = PlayerWindow()
    silence(w3)
    w3._apply_session({"subtitle_color": [999, 0, 0], "subtitle_font": "???"})
    check("不正な色は既定", w3._sub_color == (255, 255, 255), str(w3._sub_color))
    check("不正なフォントは既定", w3._sub_font == "", str(w3._sub_font))

    # 描画スモーク (新色・新フォントで例外が出ないこと)
    w.set_subtitle_color((0, 0, 0))
    w.set_subtitle_font("Meiryo")
    w.subtitle_label.setText("テスト字幕")
    w.subtitle_label.resize(320, 60)
    img = QImage(320, 60, QImage.Format.Format_ARGB32)
    img.fill(0)
    drew = True
    try:
        w.subtitle_label.render(img)
    except Exception:
        drew = False
    check("黒字幕+フォントで描画できる", drew)

    for win in (w, w2, w3):
        win.close()
    if os.path.isfile(RESUME):
        os.remove(RESUME)
    return finish("P21subcolor")


if __name__ == "__main__":
    sys.exit(main())
