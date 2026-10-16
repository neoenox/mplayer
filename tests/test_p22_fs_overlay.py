"""P22: 全画面時の操作系自動表示/フェード (マウス移動で再表示・カーソルも連動)。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, patch_message_boxes, silence, wait_until

from PySide6.QtCore import QEvent, QEventLoop, QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from main import PlayerWindow

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO = os.path.join(BASE, "test_640x360.mp4")
RESUME = os.path.join(BASE, "resume.json")


def pump(ms=0):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def send_move(widget, x=20, y=20):
    ev = QMouseEvent(QEvent.Type.MouseMove, QPointF(x, y), QPointF(x, y),
                     Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                     Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(widget, ev)


def main():
    patch_message_boxes()
    make_app()
    w = PlayerWindow()
    silence(w)
    w._resume = {}
    w._fs_hide_ms = 120  # テストでは短縮
    w.load(VIDEO)
    w.show()
    pump(120)

    check("通常時は操作系が見える", w.controls.isVisible())
    check("操作系にシーク/音量/ボタンが入る",
          w.seek.parent() is not None and w.controls.isAncestorOf(w.seek)
          and w.controls.isAncestorOf(w.vol)
          and w.controls.isAncestorOf(w.fs_btn))
    check("通常時はタイマー停止", not w._fs_timer.isActive())
    check("通常時 note_activity は無反応", (w.note_activity() or not
                                       w._fs_timer.isActive()))

    w.toggle_fullscreen()
    pump(30)
    check("全画面へ入る", w._is_fullscreen)
    check("全画面でメニューバーは隠れる", w.menuBar().isHidden())
    check("入った直後は操作系が見える", w.controls.isVisible(),
          str(w.controls.isVisible()))
    check("ボタン表示が解除に変わる", w.fs_btn.text() == "全画面解除")
    check("フェード用タイマーが動く", w._fs_timer.isActive())

    check("無操作で操作系が隠れる",
          wait_until(lambda: not w.controls.isVisible(), 3000),
          str(w.controls.isVisible()))
    check("無操作でカーソルも隠れる",
          w.cursor().shape() == Qt.CursorShape.BlankCursor,
          str(w.cursor().shape()))

    w.note_activity()
    check("操作で操作系が戻る", w.controls.isVisible())
    check("操作でカーソルも戻る",
          w.cursor().shape() != Qt.CursorShape.BlankCursor,
          str(w.cursor().shape()))
    check("再び無操作で隠れる",
          wait_until(lambda: not w.controls.isVisible(), 3000))

    # 映像領域のマウス移動 (イベントフィルタ経由) でも戻る
    send_move(w.video, 30, 30)
    pump(20)
    check("映像領域のマウス移動で戻る", w.controls.isVisible())

    check("3度目も無操作で隠れる",
          wait_until(lambda: not w.controls.isVisible(), 3000))

    w.exit_fullscreen()
    pump(30)
    check("全画面解除", not w._is_fullscreen)
    check("解除後は操作系が見える", w.controls.isVisible())
    check("解除後はカーソルが戻る",
          w.cursor().shape() != Qt.CursorShape.BlankCursor,
          str(w.cursor().shape()))
    check("解除後はメニューバーが戻る", not w.menuBar().isHidden())
    check("解除後はタイマー停止", not w._fs_timer.isActive())
    check("ボタン表示が戻る", w.fs_btn.text() == "全画面")

    # 全画面中でも再生は継続する
    w.toggle_fullscreen()
    pump(30)
    check("全画面切替後もエラーでない", w.player.error().name == "NoError",
          w.player.error().name)
    check("Esc で全画面解除できる (exit相当)",
          (w.exit_fullscreen() or (not w._is_fullscreen)),
          str(w._is_fullscreen))
    check("解除後も操作系が見える", w.controls.isVisible())

    w.player.pause()
    w.close()
    if os.path.isfile(RESUME):
        os.remove(RESUME)
    return finish("P22fsoverlay")


if __name__ == "__main__":
    sys.exit(main())
