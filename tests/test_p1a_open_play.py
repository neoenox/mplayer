"""P1a: ダイアログ経由オープン + 再生/一時停止/再開/停止 (実クリック)。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, patch_message_boxes, silence, wait_until

from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog

from main import PlayerWindow

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO = os.path.join(BASE, "test_640x360.mp4")


def main():
    patch_message_boxes()
    app = make_app()
    w = PlayerWindow()
    w.show()
    silence(w)  # 検証中は無音
    QTest.qWait(300)

    orig = QFileDialog.getOpenFileName
    QFileDialog.getOpenFileName = lambda *a, **k: (VIDEO, "")
    try:
        QTest.mouseClick(w.open_btn, Qt.MouseButton.LeftButton)
    finally:
        QFileDialog.getOpenFileName = orig
    check("dialog: playing after open_btn click",
          wait_until(lambda: w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState),
          f"title={w.windowTitle()}")
    check("dialog: title has filename", "test_640x360" in w.windowTitle())
    check("dialog: controls enabled", w.play_btn.isEnabled() and w.stop_btn.isEnabled()
          and w.seek.isEnabled())

    QTest.mouseClick(w.play_btn, Qt.MouseButton.LeftButton)
    QTest.qWait(500)
    check("click pause", w.player.playbackState() == QMediaPlayer.PlaybackState.PausedState)
    check("pause label", w.play_btn.text() == "再生", f"text={w.play_btn.text()}")
    QTest.mouseClick(w.play_btn, Qt.MouseButton.LeftButton)
    check("click resume",
          wait_until(lambda: w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState))
    QTest.mouseClick(w.stop_btn, Qt.MouseButton.LeftButton)
    QTest.qWait(800)
    # 停止 = 再生していない + 先頭に戻る (内部は pause+rewind。player.stop() は
    # Qt 6.12 FFmpegバックエンドのデッドロックを避けるため不使用)
    check("click stop halts",
          w.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState,
          f"state={w.player.playbackState()}")
    check("click stop rewinds", w.player.position() == 0, f"pos={w.player.position()}")
    return finish("P1a")


if __name__ == "__main__":
    sys.exit(main())
