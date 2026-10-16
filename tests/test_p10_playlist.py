"""P10: プレイリストと連続再生 (次の動画へ自動送り) の検証。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, patch_message_boxes, silence, wait_until

from PySide6.QtTest import QTest

from main import PlayerWindow

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO_A = os.path.join(BASE, "test_640x360.mp4")
VIDEO_B = os.path.join(BASE, "test_silent.mp4")


def main():
    patch_message_boxes()
    app = make_app()
    w = PlayerWindow()
    w.show()
    silence(w)

    check("empty: play_next returns False", w.play_next() is False)
    check("empty: play_prev returns False", w.play_prev() is False)
    check("dock hidden initially", w.pl_dock.isVisible() is False)

    added = w.add_to_playlist([VIDEO_A, VIDEO_B])
    check("add two items", added == 2 and w.playlist.count() == 2, f"count={w.playlist.count()}")
    check("dedupe on re-add", w.add_to_playlist([VIDEO_A]) == 0 and w.playlist.count() == 2)
    check("nonexistent skipped", w.add_to_playlist([os.path.join(BASE, "nope.mp4")]) == 0)
    check("dock shown after add", wait_until(lambda: w.pl_dock.isVisible(), 2000))
    check("list button checked", wait_until(lambda: w.pl_btn.isChecked(), 2000),
          f"checked={w.pl_btn.isChecked()}")

    check("play_index(0) loads A", w.play_index(0) is True)
    check("row tracks current", w.playlist.currentRow() == 0)
    check("A duration known", wait_until(lambda: w.player.duration() > 0, 8000))
    w.player.pause()

    # ダブルクリック経路で 2 番目へ
    w.playlist.itemDoubleClicked.emit(w.playlist.item(1))
    check("double-click loads B", wait_until(
        lambda: w._current_path == os.path.abspath(VIDEO_B), 8000),
        f"path={w._current_path}")
    check("row tracks double-click", w.playlist.currentRow() == 1)
    w.player.pause()

    # 前へ / 次へ
    check("play_prev -> A", w.play_prev() is True and w.playlist.currentRow() == 0)
    check("play_next -> B", w.play_next() is True and w.playlist.currentRow() == 1)
    check("next at end returns False", w.play_next() is False)

    # 連続再生: A を終端付近まで飛ばして自然に EOS させる
    w.player.pause()
    w.play_index(0)
    check("A loaded again", wait_until(
        lambda: w._current_path == os.path.abspath(VIDEO_A), 8000))
    dur = w.player.duration()
    check("A has duration", dur > 500, f"dur={dur}")
    w.player.setPosition(max(0, dur - 400))
    w.player.play()
    check("auto-advance A -> B on EOS", wait_until(
        lambda: w._current_path == os.path.abspath(VIDEO_B), 15000),
        f"path={w._current_path} status={w.player.mediaStatus()}")
    w.player.pause()

    # 削除 / クリア
    w.playlist.setCurrentRow(0)
    w.playlist.item(0).setSelected(True)
    w.remove_selected()
    check("remove_selected", w.playlist.count() == 1, f"count={w.playlist.count()}")
    w.clear_playlist()
    check("clear_playlist", w.playlist.count() == 0)

    # リストが空なら EOS で停止表示のまま
    check("empty advance guard", w._advance_if_in_playlist() is False)

    w.close()
    return finish("P10playlist")


if __name__ == "__main__":
    sys.exit(main())
