"""P1c: 音量・ミュート・全画面・リサイズ (実イベント)。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, patch_message_boxes, silence, wait_until

from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest

from main import PlayerWindow

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO = os.path.join(BASE, "test_640x360.mp4")


def main():
    patch_message_boxes()
    app = make_app()
    w = PlayerWindow()
    w.show()
    silence(w)  # 音量0 (検証中は無音)
    w.load(VIDEO)
    check("playing", wait_until(
        lambda: w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState))

    QTest.mouseClick(w.mute_btn, Qt.MouseButton.LeftButton)
    QTest.qWait(300)
    check("mute via click", w.audio.isMuted())
    QTest.mouseClick(w.mute_btn, Qt.MouseButton.LeftButton)
    QTest.qWait(300)
    check("unmute via click", not w.audio.isMuted())
    # 音量値の反映は一時停止中に検証する (停止中は出力自体がないため、
    # 音量20の瞬間も物理的に音が出ないことを保証する)
    w.player.pause()
    QTest.qWait(300)
    check("paused before volume test",
          w.player.playbackState() == QMediaPlayer.PlaybackState.PausedState)
    w.vol.setValue(20)
    check("volume 0.2", abs(w.audio.volume() - 0.2) < 0.02, f"vol={w.audio.volume()}")
    w.vol.setValue(0)
    check("volume back to 0", w.audio.volume() < 0.01, f"vol={w.audio.volume()}")
    w.player.play()
    check("resume after volume test", wait_until(
        lambda: w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState))

    QTest.mouseClick(w.fs_btn, Qt.MouseButton.LeftButton)
    QTest.qWait(400)
    check("fullscreen via button", w.isFullScreen(), f"btn={w.fs_btn.text()}")
    QTest.keyClick(w, Qt.Key.Key_Escape)
    QTest.qWait(400)
    check("exit via Esc", not w.isFullScreen())
    QTest.keyClick(w, Qt.Key.Key_F11)
    QTest.qWait(400)
    check("fullscreen via F11", w.isFullScreen())
    QTest.keyClick(w, Qt.Key.Key_F11)
    QTest.qWait(400)
    check("exit via F11", not w.isFullScreen())

    QTest.mouseDClick(w.video, Qt.MouseButton.LeftButton)
    QTest.qWait(400)
    check("fullscreen via video double-click", w.isFullScreen())
    QTest.keyClick(w, Qt.Key.Key_Escape)
    QTest.qWait(400)
    check("exit dblclick-fs via Esc", not w.isFullScreen())

    w.resize(1200, 800)
    QTest.qWait(400)
    check("aspect kept", w.video.aspectRatioMode() == Qt.AspectRatioMode.KeepAspectRatio)
    vw = w.video.size()
    check("video follows window", vw.width() > 900 and vw.height() > 400,
          f"video={vw.width()}x{vw.height()}")
    # 終了時状態: 無音 (音量0) かつ通常再生。製品既定 (80) は変えていない。
    check("ends silent (vol 0)", w.audio.volume() < 0.01, f"vol={w.audio.volume()}")
    check("ends unmuted", not w.audio.isMuted())
    return finish("P1c")


if __name__ == "__main__":
    sys.exit(main())
