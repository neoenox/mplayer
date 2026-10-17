"""P27: 字幕 ON/OFF の好みを保存し、自動読込時に尊重するか。"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(BASE, "tmp_p27")
SESSION = os.path.join(TMP, "session.json")
RESUME = os.path.join(BASE, "resume.json")

os.makedirs(TMP, exist_ok=True)
os.environ["MPLAYER_SESSION_FILE"] = SESSION
if os.path.isfile(RESUME):
    os.remove(RESUME)

from helpers import check, finish, make_app, patch_message_boxes, silence, wait_until

from PySide6.QtCore import QEventLoop, QTimer

from main import PlayerWindow

SRC = os.path.join(BASE, "test_640x360.mp4")
CLIP = os.path.join(TMP, "clip.mp4")
CLIP_SRT = os.path.join(TMP, "clip.srt")
BARE = os.path.join(TMP, "bare.mp4")  # .srt を持たない動画

SRT_TEXT = (
    "1\n"
    "00:00:00,000 --> 00:00:30,000\n"
    "字幕のテスト\n"
)


def pump(ms=0):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main():
    patch_message_boxes()
    make_app()

    shutil.copyfile(SRC, CLIP)
    shutil.copyfile(SRC, BARE)
    with open(CLIP_SRT, "w", encoding="utf-8") as f:
        f.write(SRT_TEXT)

    w = PlayerWindow()
    silence(w)
    w._resume = {}

    check("既定の好みは表示", w._subs_pref is True)
    check("既定では字幕なし", w._subs_enabled is False)

    # .srt 付き動画を開くと自動で ON
    check("動画を開く", w.load(CLIP))
    check("cues を読んだ", wait_until(lambda: len(w._cues) > 0, 3000),
          str(len(w._cues)))
    check("好みが ON なら表示される", w._subs_enabled is True)
    check("ボタンはチェック済み", w.subs_btn.isChecked() is True)
    check("ボタン表示は ON", w.subs_btn.text() == "字幕 ON", w.subs_btn.text())

    # OFF に切り替えると好みも OFF
    w.subs_btn.setChecked(False)
    w.toggle_subtitles()
    check("OFF にできる", w._subs_enabled is False)
    check("好みも OFF", w._subs_pref is False)
    check("ボタン表示が戻る", w.subs_btn.text() == "字幕", w.subs_btn.text())
    check("字幕ラベルが隠れる", w.subtitle_label.isHidden())
    check("cues は保持される", len(w._cues) > 0, str(len(w._cues)))

    # 保存 -> 復元
    w._save_session()
    with open(SESSION, encoding="utf-8") as f:
        data = json.load(f)
    check("好みが保存される", data.get("subtitles_enabled") is False,
          str(data.get("subtitles_enabled")))

    w2 = PlayerWindow()
    silence(w2)
    w2._resume = {}
    check("復元前の既定は ON", w2._subs_pref is True)
    w2._apply_session(data)
    check("OFF の好みが復元される", w2._subs_pref is False, str(w2._subs_pref))

    # 復元後: .srt 付き動画でも表示されない (cues は読む)
    check("復元後に動画を開く", w2.load(CLIP))
    check("cues は読まれる", wait_until(lambda: len(w2._cues) > 0, 3000),
          str(len(w2._cues)))
    check("好み OFF なら表示しない", w2._subs_enabled is False)
    check("ボタン表示は ON にならない", w2.subs_btn.text() == "字幕",
          w2.subs_btn.text())
    check("字幕ラベルは隠れたまま", w2.subtitle_label.isHidden())

    # 明示的に ON にすれば再読込なしで表示
    w2.subs_btn.setChecked(True)
    w2.toggle_subtitles()
    check("ON にすると表示される", w2._subs_enabled is True)
    check("好みも ON に戻る", w2._subs_pref is True)
    check("ボタン表示も ON", w2.subs_btn.text() == "字幕 ON", w2.subs_btn.text())
    pump(20)

    # 読み込み済み cues に好みを即反映
    w2.set_subtitles_pref(False)
    check("set_subtitles_pref(False) が即反映", w2._subs_enabled is False)
    check("ボタンのチェックも外れる", w2.subs_btn.isChecked() is False)
    w2.set_subtitles_pref(True)
    check("set_subtitles_pref(True) が即反映", w2._subs_enabled is True)
    check("ボタンのチェックも戻る", w2.subs_btn.isChecked() is True)
    pump(20)

    # .srt の無い動画を開いても好みは変わらない
    w2.set_subtitles_pref(False)
    check("bare を開く", w2.load(BARE))
    check("cues が無い", w2._cues == [])
    check("好みは不変 (OFF)", w2._subs_pref is False, str(w2._subs_pref))
    check("表示も OFF", w2._subs_enabled is False)
    check("字幕ボタンは OFF 表示", w2.subs_btn.text() == "字幕",
          w2.subs_btn.text())

    # 不正値は無視
    w3 = PlayerWindow()
    silence(w3)
    w3._resume = {}
    w3._apply_session({"subtitles_enabled": "yes"})
    check("不正値は無視される", w3._subs_pref is True, str(w3._subs_pref))
    w3._apply_session({"subtitles_enabled": 0})
    check("数値の不正値も無視", w3._subs_pref is True, str(w3._subs_pref))
    w3._apply_session({"subtitles_enabled": False})
    check("False は反映される", w3._subs_pref is False, str(w3._subs_pref))

    # セッション未保存 (キーなし) でも既定 ON のまま
    w4 = PlayerWindow()
    silence(w4)
    w4._resume = {}
    w4._apply_session({})
    check("キーが無ければ既定 ON", w4._subs_pref is True)

    for win in (w, w2, w3, w4):
        win.player.pause()
    w4.close()
    w3.close()
    w2.close()
    w.close()
    if os.path.isfile(RESUME):
        os.remove(RESUME)
    if os.path.isfile(SESSION):
        os.remove(SESSION)
    shutil.rmtree(TMP, ignore_errors=True)
    return finish("P27subtitlepref")


if __name__ == "__main__":
    sys.exit(main())
