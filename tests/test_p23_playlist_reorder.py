"""P23: プレイリストの並べ替え (ドラッグ内部移動 / 上下ボタン) と保存順の維持。"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(BASE, "tmp_p23")
SESSION = os.path.join(TMP, "session.json")
RESUME = os.path.join(BASE, "resume.json")

os.makedirs(TMP, exist_ok=True)
os.environ["MPLAYER_SESSION_FILE"] = SESSION
if os.path.isfile(RESUME):
    os.remove(RESUME)

from helpers import check, finish, make_app, patch_message_boxes, silence, wait_until

from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtWidgets import QAbstractItemView

from main import PlayerWindow

SRC = os.path.join(BASE, "test_640x360.mp4")


def pump(ms=0):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def setup_files():
    if os.path.isdir(TMP):
        for n in os.listdir(TMP):
            p = os.path.join(TMP, n)
            if os.path.isfile(p) and n != "session.json":
                os.remove(p)
    out = []
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        dst = os.path.join(TMP, name)
        shutil.copyfile(SRC, dst)
        out.append(os.path.abspath(dst))
    return out


def names(paths):
    return [os.path.basename(p) for p in paths]


def main():
    patch_message_boxes()
    app = make_app()
    A, B, C = setup_files()
    w = PlayerWindow()
    silence(w)
    w._resume = {}

    added = w.add_to_playlist([A, B, C])
    check("3件を追加できる", added == 3, str(added))
    check("表示順は追加順", names(w.playlist_paths()) == ["a.mp4", "b.mp4", "c.mp4"],
          str(names(w.playlist_paths())))
    check("playlist_paths は絶対パスを返す",
          all(os.path.isabs(p) for p in w.playlist_paths()))

    # ドラッグ並べ替えの設定
    check("内部移動モードが有効",
          w.playlist.dragDropMode() == QAbstractItemView.DragDropMode.InternalMove,
          str(w.playlist.dragDropMode()))
    check("ドラッグ開始が有効", w.playlist.dragEnabled())
    check("ドロップ受け入れが有効", w.playlist.acceptDrops())
    check("ドロップ位置表示が有効", w.playlist.showDropIndicator())
    check("選択は単一",
          w.playlist.selectionMode() == QAbstractItemView.SelectionMode.SingleSelection,
          str(w.playlist.selectionMode()))
    check("上下ボタンがある",
          w.pl_up_btn.text() == "上へ" and w.pl_down_btn.text() == "下へ",
          f"{w.pl_up_btn.text()}/{w.pl_down_btn.text()}")

    # 上へ/下へ (選択項目の移動)
    w.playlist.setCurrentRow(0)
    check("先頭を下へ動かせる", w.move_selected(+1) is True)
    check("並びが入れ替わる (b,a,c)",
          names(w.playlist_paths()) == ["b.mp4", "a.mp4", "c.mp4"],
          str(names(w.playlist_paths())))
    check("移動した項目が選択されたまま", w.playlist.currentRow() == 1,
          str(w.playlist.currentRow()))
    check("上へで元に戻る", w.move_selected(-1) is True)
    check("並びが戻る (a,b,c)",
          names(w.playlist_paths()) == ["a.mp4", "b.mp4", "c.mp4"],
          str(names(w.playlist_paths())))
    check("選択が追従 (0)", w.playlist.currentRow() == 0,
          str(w.playlist.currentRow()))

    # 端での挙動
    check("先頭より上へは不可", w.move_selected(-1) is False)
    check("端で並びは不変",
          names(w.playlist_paths()) == ["a.mp4", "b.mp4", "c.mp4"])
    w.playlist.setCurrentRow(2)
    check("末尾より下へは不可", w.move_selected(+1) is False)
    check("端で並びは不変(末尾)",
          names(w.playlist_paths()) == ["a.mp4", "b.mp4", "c.mp4"])
    check("delta 0 は何もしない", w.move_selected(0) is False)

    # 未選択
    w.playlist.clearSelection()
    w.playlist.setCurrentRow(-1)
    check("未選択では移動しない", w.move_selected(+1) is False,
          str(w.playlist.currentRow()))
    check("未選択で並びは不変",
          names(w.playlist_paths()) == ["a.mp4", "b.mp4", "c.mp4"])

    # ドラッグ内部移動と同じデータ経路 (モデル moveRow)
    moved = w.playlist.model().moveRow(w.playlist.rootIndex(), 0,
                                      w.playlist.rootIndex(), 3)
    check("モデルの行移動が成功", moved is True, str(moved))
    check("ドラッグ移動で末尾へ (b,c,a)",
          names(w.playlist_paths()) == ["b.mp4", "c.mp4", "a.mp4"],
          str(names(w.playlist_paths())))

    # 並べ替え後の選択/再生整合
    w.playlist.setCurrentRow(2)
    w._current_path = os.path.abspath(A)
    check("現在項目の行を再検出", w._index_of_current() == 2,
          str(w._index_of_current()))
    check("並べ替え後も再生できる", w.play_index(0) is True)
    check("再生中のパスが一致",
          w._current_path == os.path.abspath(B), str(w._current_path))
    check("次へで正しい順に進む",
          (w.play_next() is True) and w._current_path == os.path.abspath(C),
          str(w._current_path))
    w.player.pause()

    # 保存順 = 表示順
    order_expected = ["b.mp4", "c.mp4", "a.mp4"]
    w._save_session()
    with open(SESSION, encoding="utf-8") as f:
        data = json.load(f)
    check("保存した順序が表示順と一致",
          names(data.get("playlist", [])) == order_expected,
          str(names(data.get("playlist", []))))
    check("保存順は名前順とは異なる (並べ替えが保存された)",
          names(data["playlist"]) != sorted(order_expected),
          str(names(data["playlist"])))

    # 別ウィンドウで復元しても同じ順序
    w2 = PlayerWindow()
    silence(w2)
    w2._resume = {}
    check("復元前は空", w2.playlist.count() == 0)
    w2._apply_session(data)
    check("復元後も同じ順序",
          names(w2.playlist_paths()) == order_expected,
          str(names(w2.playlist_paths())))
    check("復元件数が一致", w2.playlist.count() == 3,
          str(w2.playlist.count()))

    # 削除・クリアの維持
    w2.playlist.setCurrentRow(0)
    w2.remove_selected()
    check("選択項目を削除できる",
          names(w2.playlist_paths()) == ["c.mp4", "a.mp4"],
          str(names(w2.playlist_paths())))
    w2.clear_playlist()
    check("クリアで空になる", w2.playlist.count() == 0)
    check("クリア後の playlist_paths は空", w2.playlist_paths() == [])

    # 重複追加は無視され順序も維持
    check("重複は追加されない",
          w.add_to_playlist([os.path.abspath(B)]) == 0)
    check("重複追加後も順序は不変",
          names(w.playlist_paths()) == order_expected,
          str(names(w.playlist_paths())))

    w.player.pause()
    w2.close()
    w.close()
    if os.path.isfile(RESUME):
        os.remove(RESUME)
    if os.path.isfile(SESSION):
        os.remove(SESSION)
    shutil.rmtree(TMP, ignore_errors=True)
    return finish("P23playlistreorder")


if __name__ == "__main__":
    sys.exit(main())
