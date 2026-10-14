"""P1d: DnD・再生中切替・再生中close (実イベント)。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, patch_message_boxes, silence, wait_until

from PySide6.QtCore import Qt, QMimeData, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest

from main import PlayerWindow

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO = os.path.join(BASE, "test_640x360.mp4")
VIDEO2 = os.path.join(BASE, "test_silent.mp4")


def drop(window, path):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(path)])
    pos = window.rect().center()
    drag = QDragEnterEvent(pos, Qt.DropAction.CopyAction, mime,
                           Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    window.dragEnterEvent(drag)
    de = QDropEvent(pos, Qt.DropAction.CopyAction, mime,
                    Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    window.dropEvent(de)
    return drag.isAccepted(), de.isAccepted()


def main():
    patch_message_boxes()
    app = make_app()
    w = PlayerWindow()
    w.show()
    silence(w)  # 検証中は無音
    w.load(VIDEO)
    check("playing", wait_until(
        lambda: w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState))

    da, pa = drop(w, VIDEO2)
    check("dragEnter accepted", da)
    check("drop switches file", wait_until(lambda: "test_silent" in w.windowTitle(), 8000),
          f"title={w.windowTitle()}")

    for i in range(3):
        w.load(VIDEO if i % 2 == 0 else VIDEO2)
        QTest.qWait(700)
    check("switch storm survives", wait_until(
        lambda: w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState, 8000))

    import subprocess
    # 実行中と同じインタプリタ (クリーンvenv検証時はそちら) を使う
    exe = sys.executable
    try:
        cp = subprocess.run([exe, "-u", os.path.join(BASE, "tests", "close_check.py")],
                            cwd=BASE, capture_output=True, text=True, timeout=30,
                            errors="replace")
        check("close while playing quits cleanly", cp.returncode == 0,
              f"exit={cp.returncode} tail={(cp.stdout or '')[-200:]}")
    except subprocess.TimeoutExpired:
        check("close while playing quits cleanly", False, "subprocess timeout (quit hang)")
    except Exception as e:
        check("close while playing quits cleanly", False, str(e))
    return finish("P1d")


if __name__ == "__main__":
    sys.exit(main())
