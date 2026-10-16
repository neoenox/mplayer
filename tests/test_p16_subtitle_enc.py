"""P16: 字幕の文字コード自動判定と縁取り表示の検証。"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, patch_message_boxes

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPalette

import main as app_main
from main import (SUB_ENCODINGS, PlayerWindow, SubtitleLabel,
                  decode_subtitle_bytes, parse_srt)

SRT = ("1\n00:00:01,000 --> 00:00:03,000\nこんにちは、世界\n\n"
       "2\n00:00:04,000 --> 00:00:06,000\n二行目\nです\n\n")
SRT_UTF8 = SRT.encode("utf-8")
SRT_UTF8_BOM = b"\xef\xbb\xbf" + SRT_UTF8
SRT_CP932 = SRT.encode("cp932")
SRT_UTF16 = SRT.encode("utf-16")


def main():
    patch_message_boxes()

    # ---- 復号 (auto) ----
    text, used = decode_subtitle_bytes(SRT_UTF8)
    check("auto utf-8 を検出", used == "utf-8" and "こんにちは" in text, used)

    text, used = decode_subtitle_bytes(SRT_UTF8_BOM)
    check("auto BOM付きUTF-8 を検出", used == "utf-8" and "こんにちは" in text, used)

    text, used = decode_subtitle_bytes(SRT_CP932)
    check("auto Shift_JIS(CP932) を検出", used == "cp932" and "こんにちは" in text, used)

    text, used = decode_subtitle_bytes(SRT_UTF16)
    check("auto UTF-16(BOM) を検出", used == "utf-16" and "こんにちは" in text, used)

    # ---- 復号 (明示指定 / フォールバック) ----
    text, used = decode_subtitle_bytes(SRT_CP932, "cp932")
    check("明示 cp932 で復号", "こんにちは" in text, used)

    text, used = decode_subtitle_bytes(SRT_CP932, "utf-8")
    check("utf-8 指定でも日本語化けを回避 (自動へフォールバック)",
          "こんにちは" in text, f"used={used}")
    text, used = decode_subtitle_bytes(SRT_UTF8, "cp932")
    check("cp932 指定でも UTF-8 を正しく復号", "こんにちは" in text, f"used={used}")

    # ---- parse との結合 ----
    cues = parse_srt(decode_subtitle_bytes(SRT_CP932)[0])
    check("CP932 から 2 キュー", len(cues) == 2, f"{len(cues)}")
    check("CP932 本文が正しい", cues[0][2] == "こんにちは、世界", repr(cues[0][2]))
    check("CP932 複数行本文", cues[1][2] == "二行目\nです", repr(cues[1][2]))

    # ---- 縁取りの描画 ----
    make_app()
    label = SubtitleLabel()
    label.setText("字幕")
    label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
    label.resize(220, 90)
    font = label.font()
    font.setPixelSize(40)
    label.setFont(font)
    # 背景色を白に固定し、縁取り(黒)と塗り(白)だけを数えられるようにする
    pal = label.palette()
    pal.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.white)
    label.setPalette(pal)

    def _count(img):
        dark = white = 0
        for y in range(img.height()):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                if c.alpha() > 200:
                    if c.red() < 60 and c.green() < 60 and c.blue() < 60:
                        dark += 1
                    if c.red() > 220 and c.green() > 220 and c.blue() > 220:
                        white += 1
        return dark, white

    def _render():
        img = QImage(220, 90, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        label.render(img)
        return img

    label.set_outline(True, 2.0)
    dark_on, white_on = _count(_render())
    check("縁取りONで黒い縁ピクセルが存在", dark_on > 100, f"{dark_on}")
    check("縁取りONで白い塗りピクセルが存在", white_on > 100, f"{white_on}")

    label.set_outline(False)
    dark_off, white_off = _count(_render())
    check("縁取りOFFで黒ピクセルなし", dark_off == 0, f"{dark_off}")
    check("縁取りOFFで白文字は描画", white_off > 100, f"{white_off}")
    check("縁取りの有無で描画が変化", dark_on - dark_off > 100,
          f"on={dark_on} off={dark_off}")
    label.close()

    # ---- ウィンドウ統合 ----
    w = PlayerWindow()
    check("subtitle_label は SubtitleLabel",
          isinstance(w.subtitle_label, SubtitleLabel))
    check("縁取りは既定でON", w._sub_outline is True
          and w.subtitle_label.outline() is True)
    check("メニュー縁取りはチェック済み", w._sub_outline_act.isChecked())
    check("文字コードは3択", len(w._sub_enc_group.actions()) == len(SUB_ENCODINGS)
          and set(SUB_ENCODINGS) == set(app_main.SUB_ENCODINGS))
    auto_checked = [a.text() for a in w._sub_enc_group.actions() if a.isChecked()]
    check("既定は『自動』", auto_checked == ["自動"], f"{auto_checked}")

    d = tempfile.mkdtemp(prefix="mplayer_sub_")
    sjis = os.path.join(d, "jp.srt")
    with open(sjis, "wb") as f:
        f.write(SRT_CP932)
    check("Shift_JIS の SRT を読込", w.load_subtitles(sjis) and len(w._cues) == 2)
    check("読込本文が化けていない", w._cues[0][2] == "こんにちは、世界",
          repr(w._cues[0][2]))
    check("採用文字コードを記録", w._sub_used_encoding == "cp932",
          w._sub_used_encoding)
    check("現在の字幕パスを保持", w._current_sub_path == sjis)

    utf = os.path.join(d, "utf.srt")
    with open(utf, "wb") as f:
        f.write(SRT_UTF8)
    w.set_subtitle_encoding("utf-8")
    w.load_subtitles(utf)
    check("UTF-8 へ切替できる", w._sub_used_encoding == "utf-8",
          w._sub_used_encoding)
    check("切替後も本文は正しい", w._cues[0][2] == "こんにちは、世界")

    # 文字コード変更で再読込 (現在の字幕)
    w.load_subtitles(sjis)
    w.set_subtitle_encoding("auto")
    check("auto へ戻すと再読込される", w._current_sub_path == sjis
          and w._sub_used_encoding == "cp932", w._sub_used_encoding)

    w.set_subtitle_outline(False)
    check("set_subtitle_outline(False) が反映", w._sub_outline is False
          and w.subtitle_label.outline() is False
          and not w._sub_outline_act.isChecked())
    w.set_subtitle_outline(True)

    # ---- セッション保存/復元 ----
    w.set_subtitle_outline(False)
    w.set_subtitle_encoding("cp932")
    w._save_session()
    with open(app_main.SESSION_FILE, encoding="utf-8") as f:
        data = json.load(f)
    check("session に subtitle_outline", data.get("subtitle_outline") is False)
    check("session に subtitle_encoding", data.get("subtitle_encoding") == "cp932")

    w2 = PlayerWindow()
    w2._apply_session(data)
    check("復元: 縁取りOFF", w2._sub_outline is False
          and w2.subtitle_label.outline() is False)
    check("復元: 文字コード cp932", w2._sub_encoding == "cp932")
    cp932_checked = [a.text() for a in w2._sub_enc_group.actions() if a.isChecked()]
    check("復元: メニューが Shift_JIS 選択", cp932_checked == ["Shift_JIS"],
          f"{cp932_checked}")

    w2.close()
    w.close()
    return finish("P16subenc")


if __name__ == "__main__":
    sys.exit(main())
