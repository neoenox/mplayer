"""P24: 字幕の背景帯 ON/OFF (描画・メニュー・セッション保存)。"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(BASE, "tmp_p24")
SESSION = os.path.join(TMP, "session.json")
RESUME = os.path.join(BASE, "resume.json")

os.makedirs(TMP, exist_ok=True)
os.environ["MPLAYER_SESSION_FILE"] = SESSION
if os.path.isfile(RESUME):
    os.remove(RESUME)

from helpers import check, finish, make_app, patch_message_boxes, silence

from PySide6.QtCore import QEventLoop, QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QImage, QPainter, QRegion
from PySide6.QtWidgets import QWidget

from main import SubtitleLabel, PlayerWindow

VIDEO = os.path.join(BASE, "test_640x360.mp4")
SRT = os.path.join(TMP, "clip.srt")
CLIP = os.path.join(TMP, "clip.mp4")

SRT_TEXT = (
    "1\n"
    "00:00:00,000 --> 00:00:30,000\n"
    "背景帯のテスト\n"
)


def pump(ms=0):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def render(label, width=300, height=80) -> QImage:
    """ラベル自身を透過キャンバスへ描画する (grab は背景を塗るため使わない)。"""
    label.resize(width, height)
    img = QImage(width, height, QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    label.render(p, QPoint(0, 0), QRegion(), QWidget.RenderFlag.DrawChildren)
    p.end()
    return img


def bg_alpha(label) -> int:
    """背景帯の不透明度 (余白部分) を返す。"""
    img = render(label)
    if img.isNull() or img.width() < 3 or img.height() < 3:
        return -1
    return img.pixelColor(2, 2).alpha()


def main():
    patch_message_boxes()
    make_app()

    shutil.copyfile(VIDEO, CLIP)
    with open(SRT, "w", encoding="utf-8") as f:
        f.write(SRT_TEXT)

    # --- ラベル単体の描画 ---
    lbl = SubtitleLabel()
    lbl.setText("背景帯のテスト\n二行目")
    check("ラベル既定は背景帯 ON", lbl.bg_enabled() is True)
    on = bg_alpha(lbl)
    check("ON で半透明帯を描く", on == 150, str(on))
    lbl.set_bg_enabled(False)
    check("ラベル OFF 反映", lbl.bg_enabled() is False)
    off = bg_alpha(lbl)
    check("OFF で帯を描かない", off == 0, str(off))
    lbl.set_bg_enabled(True)
    check("再度 ON で描く", bg_alpha(lbl) == 150)
    lbl.deleteLater()

    # --- ウィンドウ側 ---
    w = PlayerWindow()
    silence(w)
    w._resume = {}
    w.load(CLIP)
    w.subtitle_label.setText("背景帯のテスト\n二行目")
    pump(50)

    check("ウィンドウ既定は ON", w._sub_bg is True)
    check("ラベル側も ON", w.subtitle_label.bg_enabled() is True)
    check("メニュー項目がある", hasattr(w, "_sub_bg_act"))
    check("メニューは背景帯", w._sub_bg_act.text() == "背景帯",
          w._sub_bg_act.text())
    check("メニューはチェック可能", w._sub_bg_act.isCheckable())
    check("メニューもチェック済み", w._sub_bg_act.isChecked())
    check("メニューで描画される", bg_alpha(w.subtitle_label) == 150)

    # OFF (メソッド)
    w.set_subtitle_bg(False)
    check("OFF が反映される", w._sub_bg is False)
    check("ラベル側も OFF", w.subtitle_label.bg_enabled() is False)
    check("メニューのチェックが外れる", not w._sub_bg_act.isChecked())
    check("OFF で描画されない", bg_alpha(w.subtitle_label) == 0)

    # メニュー経由 (activate = 実際のクリック相当。チェックは内部でトグルされる)
    check("クリック前は未チェック", not w._sub_bg_act.isChecked())
    w._sub_bg_act.activate(QAction.ActionEvent.Trigger)
    check("メニュー操作で ON に戻る", w._sub_bg is True)
    check("ラベル側も ON に戻る", w.subtitle_label.bg_enabled() is True)
    check("再度描画される", bg_alpha(w.subtitle_label) == 150)

    # 他の字幕設定と独立
    w.set_subtitle_outline(False)
    check("縁取り OFF でも背景帯は ON のまま", w._sub_bg is True)
    w.set_subtitle_bg(False)
    check("背景帯 OFF でも縁取り状態は不変", w._sub_outline is False)
    w.set_subtitle_size(24)
    check("サイズ変更で背景帯設定が維持される", w._sub_bg is False,
          str(w._sub_bg))
    w.set_subtitle_pos("top")
    check("位置変更で背景帯設定が維持される", w._sub_bg is False,
          str(w._sub_bg))
    w.set_subtitle_pos("bottom")
    w.set_subtitle_size(18)
    w.set_subtitle_outline(True)

    # 保存 -> 復元
    w._save_session()
    with open(SESSION, encoding="utf-8") as f:
        data = json.load(f)
    check("背景帯設定が保存される", data.get("subtitle_bg") is False,
          str(data.get("subtitle_bg")))

    w2 = PlayerWindow()
    silence(w2)
    w2._resume = {}
    check("復元前は既定 ON", w2._sub_bg is True)
    w2._apply_session(data)
    check("OFF が復元される", w2._sub_bg is False, str(w2._sub_bg))
    check("復元後ラベルも OFF", w2.subtitle_label.bg_enabled() is False)
    check("復元後メニューのチェックも外れる", not w2._sub_bg_act.isChecked())

    w3 = PlayerWindow()
    silence(w3)
    w3._resume = {}
    w3._apply_session({"subtitle_bg": "no"})
    check("不正値は無視される", w3._sub_bg is True, str(w3._sub_bg))
    w3._apply_session({"subtitle_bg": 0})
    check("数値などの不正値も無視", w3._sub_bg is True, str(w3._sub_bg))
    w3._apply_session({"subtitle_bg": True})
    check("True は反映される", w3._sub_bg is True)

    w.player.pause()
    w2.close()
    w3.close()
    w.close()
    if os.path.isfile(RESUME):
        os.remove(RESUME)
    if os.path.isfile(SESSION):
        os.remove(SESSION)
    shutil.rmtree(TMP, ignore_errors=True)
    return finish("P24subtitlebg")


if __name__ == "__main__":
    sys.exit(main())
