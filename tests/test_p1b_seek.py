"""P1b: シークバー実ドラッグ + 再生位置同期。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, patch_message_boxes, silence, wait_until

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from main import PlayerWindow, format_ms

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO = os.path.join(BASE, "test_640x360.mp4")


def main():
    patch_message_boxes()
    app = make_app()
    w = PlayerWindow()
    w.show()
    silence(w)  # 検証中は無音
    w.load(VIDEO)
    check("duration ready", wait_until(lambda: w.player.duration() > 4000, 10000),
          f"dur={w.player.duration()}")
    w.player.pause()
    QTest.qWait(400)
    s = w.seek
    gx, y = s.width() - 8, s.height() // 2
    QTest.mousePress(s, Qt.MouseButton.LeftButton, pos=QPoint(gx, y))
    QTest.mouseMove(s, QPoint(gx - 60, y))
    QTest.mouseRelease(s, Qt.MouseButton.LeftButton, pos=QPoint(gx - 60, y))
    # ドラッグ先はウィジェット幅に依存するため、固定値ではなく
    # 「スライダー値に位置が追従し、ラベルが位置と同期する」ことを検証する。
    target = s.value()
    check("drag moved seek target", target >= 3000, f"target={target}")
    check("position follows drag",
          wait_until(lambda: abs(w.player.position() - target) <= 300, 8000),
          f"target={target} pos={w.player.position()}")
    pos = w.player.position()
    expected = format_ms(pos)
    check("time label syncs with position", w.time_label.text().startswith(expected),
          f"label={w.time_label.text()} expected={expected}")
    return finish("P1b")


if __name__ == "__main__":
    sys.exit(main())
