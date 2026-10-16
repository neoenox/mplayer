"""P6: ショートカットキー + 再生速度の自動検証 (実キーイベント・無音)。

Space=再生/一時停止、Left/Right=∓5秒、F=全画面、M=ミュート、
Up/Down=音量±10、速度ボタン=0.5→1→1.5→2倍循環。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, patch_message_boxes, silence, wait_until

from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest

from main import PlayerWindow

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO = os.path.join(BASE, "test_60s.mp4")  # 60秒 (シーク幅の検証用)


def main():
    patch_message_boxes()
    app = make_app()
    w = PlayerWindow()
    w.show()
    silence(w)
    w.load(VIDEO)
    check("playing", wait_until(
        lambda: w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState, 10000))
    check("duration", wait_until(lambda: w.player.duration() > 4000, 10000))

    # Space: 一時停止→再生 (二重発火なし)
    QTest.keyClick(w, Qt.Key.Key_Space)
    QTest.qWait(500)
    check("space pauses", w.player.playbackState() == QMediaPlayer.PlaybackState.PausedState)
    QTest.keyClick(w, Qt.Key.Key_Space)
    check("space resumes", wait_until(
        lambda: w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState, 8000))

    # Right/Left: シーク (安全な遅延経路)
    w.player.pause()
    QTest.qWait(300)
    w.player.setPosition(20000)
    QTest.qWait(800)
    QTest.keyClick(w, Qt.Key.Key_Right)
    check("right seeks +5s", wait_until(lambda: 24000 <= w.player.position() <= 27000, 8000),
          f"pos={w.player.position()}")
    QTest.keyClick(w, Qt.Key.Key_Left)
    QTest.keyClick(w, Qt.Key.Key_Left)
    check("left seeks -10s", wait_until(lambda: 13000 <= w.player.position() <= 17000, 8000),
          f"pos={w.player.position()}")
    w.player.play()

    # F: 全画面 / Esc解除
    QTest.keyClick(w, Qt.Key.Key_F)
    QTest.qWait(400)
    check("F fullscreen", w.isFullScreen())
    QTest.keyClick(w, Qt.Key.Key_Escape)
    QTest.qWait(400)
    check("Esc exits", not w.isFullScreen())

    # M: ミュート切替
    QTest.keyClick(w, Qt.Key.Key_M)
    QTest.qWait(300)
    check("M mutes", w.audio.isMuted())
    QTest.keyClick(w, Qt.Key.Key_M)
    QTest.qWait(300)
    check("M unmutes", not w.audio.isMuted())

    # Up/Down: 音量 (無音域で検証: 0→Up→10→Down→0)
    check("vol starts 0", w.vol.value() == 0, f"v={w.vol.value()}")
    QTest.keyClick(w, Qt.Key.Key_Up)
    QTest.qWait(200)
    check("Up +10", w.vol.value() == 10, f"v={w.vol.value()}")
    QTest.keyClick(w, Qt.Key.Key_Down)
    QTest.qWait(200)
    check("Down -10", w.vol.value() == 0, f"v={w.vol.value()}")

    # 速度ボタン: 1.0→1.5→2.0→0.5→1.0
    check("rate default 1.0", abs(w.player.playbackRate() - 1.0) < 1e-6)
    for expect in (1.5, 2.0, 0.5, 1.0):
        QTest.mouseClick(w.speed_btn, Qt.MouseButton.LeftButton)
        QTest.qWait(300)
        check(f"rate {expect}x", abs(w.player.playbackRate() - expect) < 1e-6,
              f"rate={w.player.playbackRate()} btn={w.speed_btn.text()}")
    check("still playing at 1.0x",
          w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)

    return finish("P6features")


if __name__ == "__main__":
    sys.exit(main())
