"""P25: 映像上のマウスホイールで音量調整 (段階/clamp/ミュート解除/全画面)。"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(BASE, "tmp_p25")
SESSION = os.path.join(TMP, "session.json")
RESUME = os.path.join(BASE, "resume.json")

os.makedirs(TMP, exist_ok=True)
os.environ["MPLAYER_SESSION_FILE"] = SESSION
if os.path.isfile(RESUME):
    os.remove(RESUME)

from helpers import check, finish, make_app, patch_message_boxes, silence, wait_until

from PySide6.QtCore import QEventLoop, QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget

from main import VOLUME_STEP, PlayerWindow

VIDEO = os.path.join(BASE, "test_640x360.mp4")


def pump(ms=0):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def wheel(widget, up=True):
    dy = 120 if up else -120
    pos = QPointF(10.0, 10.0)
    ev = QWheelEvent(pos, pos, QPoint(0, 0), QPoint(0, dy),
                     Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                     Qt.ScrollPhase.NoScrollPhase, False)
    return QApplication.sendEvent(widget, ev)


def main():
    patch_message_boxes()
    app = make_app()
    w = PlayerWindow()
    silence(w)
    w._resume = {}
    w.load(VIDEO)
    w.show()
    pump(50)

    check("音量ステップは 5", VOLUME_STEP == 5, str(VOLUME_STEP))
    check("フィルタ対象に映像がある", w.video is not None)

    w.vol.setValue(50)
    check("基準音量 50", w.vol.value() == 50, str(w.vol.value()))

    # 映像上でホイール
    handled = wheel(w.video, up=True)
    pump(10)
    check("上方向が処理される", handled is True, str(handled))
    check("上で +5", w.vol.value() == 55, str(w.vol.value()))
    wheel(w.video, up=False)
    pump(10)
    check("下で -5", w.vol.value() == 50, str(w.vol.value()))
    wheel(w.video, up=True)
    pump(10)
    check("連続で交互に効く", w.vol.value() == 55, str(w.vol.value()))

    # clamp
    w.vol.setValue(100)
    wheel(w.video, up=True)
    pump(10)
    check("上限 100 で止まる", w.vol.value() == 100, str(w.vol.value()))
    w.vol.setValue(0)
    wheel(w.video, up=False)
    pump(10)
    check("下限 0 で止まる", w.vol.value() == 0, str(w.vol.value()))

    # nudge_volume の戻り値
    check("上方向は変化ありで True", w.nudge_volume(VOLUME_STEP) is True)
    check("0 は変化なしで False", w.nudge_volume(0) is False)
    w.vol.setValue(100)
    check("上限で False", w.nudge_volume(VOLUME_STEP) is False)
    w.vol.setValue(0)
    check("下限で False", w.nudge_volume(-VOLUME_STEP) is False)

    # ミュート中のホイールは解除して音量が効く
    w.vol.setValue(50)
    w.mute_btn.setChecked(True)
    w.audio.setMuted(True)
    check("ミュート状態を作る", w.mute_btn.isChecked() is True)
    wheel(w.video, up=True)
    pump(10)
    check("ホイールで音量が上がる", w.vol.value() == 55, str(w.vol.value()))
    check("ミュートが解除される", w.mute_btn.isChecked() is False,
          str(w.mute_btn.isChecked()))
    check("audio もミュート解除", w.audio.isMuted() is False)

    # 映像以外 (コントロール) のホイールは横取りしない
    w.vol.setValue(50)
    vol_before = w.vol.value()
    wheel(w.controls, up=True)
    pump(10)
    check("コントロール上では音量が変わらない", w.vol.value() == vol_before,
          str(w.vol.value()))
    w._save_session()
    with open(SESSION, encoding="utf-8") as f:
        check("保存音量も不変", json.load(f).get("volume") == vol_before)

    # 全画面: ホイールで操作系が再表示される
    w._fs_hide_ms = 120
    w.toggle_fullscreen()
    pump(30)
    check("全画面へ入る", w._is_fullscreen is True)
    check("無操作で操作系が隠れる",
          wait_until(lambda: not w.controls.isVisible(), 3000))
    wheel(w.video, up=True)
    pump(20)
    check("ホイールで操作系が戻る", w.controls.isVisible() is True)
    check("全画面でも音量が変わる", w.vol.value() == 55, str(w.vol.value()))
    w.exit_fullscreen()
    pump(30)
    check("全画面を解除", w._is_fullscreen is False)

    # 音量はセッションに保存される
    w.vol.setValue(35)
    w._save_session()
    with open(SESSION, encoding="utf-8") as f:
        data = json.load(f)
    check("保存した音量が一致", data.get("volume") == 35, str(data.get("volume")))

    w.player.pause()
    w.close()
    if os.path.isfile(RESUME):
        os.remove(RESUME)
    if os.path.isfile(SESSION):
        os.remove(SESSION)
    shutil.rmtree(TMP, ignore_errors=True)
    return finish("P25wheelvolume")


if __name__ == "__main__":
    sys.exit(main())
