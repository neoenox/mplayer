"""Regression checks for issues #1 and #2 (real Qt events, silent playback)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, silence, wait_until
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtMultimedia import QMediaPlayer
from main import PlayerWindow
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main():
    app = make_app()
    w = PlayerWindow()
    w.show()
    silence(w)
    w.load(os.path.join(BASE, 'test_60s.mp4'))
    check('duration ready', wait_until(lambda: w.player.duration() == 60000))
    w.player.pause()
    QTest.qWait(200)
    w.seek.setFocus()
    QTest.keyClick(w.seek, Qt.Key.Key_PageUp)
    target = w.seek.value()
    check('keyboard seek applied', wait_until(lambda: w.player.position() == target, 2000),
          f'target={target} pos={w.player.position()}')
    QTest.keyClick(w.seek, Qt.Key.Key_Home)
    check('Home rewinds', wait_until(lambda: w.player.position() == 0, 2000))
    w.stop()
    w.load(os.path.join(BASE, 'test_640x360.mp4'))
    QTest.qWait(1200)
    check('new video keeps playing after stale stop',
          w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState and w.player.position() > 0)
    w.stop()
    check('normal stop rewinds and pauses', wait_until(lambda:
          w.player.position() == 0 and w.player.playbackState() == QMediaPlayer.PlaybackState.PausedState))
    w.close()
    return finish('P6')

if __name__ == '__main__':
    sys.exit(main())

