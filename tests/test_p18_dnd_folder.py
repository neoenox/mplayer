"""P18: フォルダのドラッグ&ドロップ (中の動画をまとめてプレイリストへ)。"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, patch_message_boxes, silence, wait_until

from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent

from main import (DROP_MAX_FILES, PlayerWindow, collect_video_files,
                  is_video_file)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(BASE, "test_640x360.mp4")
RESUME = os.path.join(BASE, "resume.json")


def drop(w, paths):
    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile(p) for p in paths])
    ev = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, md,
                    Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    w.dropEvent(ev)
    return ev


def main():
    patch_message_boxes()

    check("判定: .mp4", is_video_file("a.mp4"))
    check("判定: 大文字 .MP4", is_video_file("A.MP4"))
    check("判定: .mkv", is_video_file("a.mkv"))
    check("判定: .srt は動画でない", not is_video_file("a.srt"))
    check("判定: .txt は動画でない", not is_video_file("a.txt"))

    tmp = tempfile.mkdtemp(prefix="mplayer_p18_")
    sub = os.path.join(tmp, "sub")
    hidden = os.path.join(tmp, ".hidden")
    os.makedirs(sub)
    os.makedirs(hidden)
    shutil.copyfile(SAMPLE, os.path.join(tmp, "a.mp4"))
    shutil.copyfile(SAMPLE, os.path.join(sub, "b.mp4"))
    with open(os.path.join(sub, "c.txt"), "w", encoding="utf-8") as f:
        f.write("x")
    shutil.copyfile(SAMPLE, os.path.join(hidden, "d.mp4"))
    with open(os.path.join(tmp, "e.srt"), "w", encoding="utf-8") as f:
        f.write("1\n00:00:00,000 --> 00:00:01,000\nhello\n")

    got = collect_video_files(tmp)
    check("フォルダ: 動画のみ収集", len(got) == 2, f"{got}")
    check("フォルダ: ルート直下が先頭", os.path.basename(got[0]) == "a.mp4")
    check("フォルダ: サブフォルダも含む",
          os.path.basename(got[1]) == "b.mp4" and "sub" in got[1])
    check("フォルダ: 隠しフォルダは除外", all(".hidden" not in p for p in got))
    check("フォルダ: 非動画は除外", all(p.lower().endswith(".mp4") for p in got))
    check("フォルダ: 非再帰は直下のみ",
          [os.path.basename(p) for p in collect_video_files(tmp, recursive=False)]
          == ["a.mp4"])
    check("フォルダ: limit で打ち切り", len(collect_video_files(tmp, limit=1)) == 1)
    check("ファイル単体を渡すとそれ自身",
          collect_video_files(os.path.join(tmp, "a.mp4")) ==
          [os.path.join(tmp, "a.mp4")])
    check("非動画ファイルは空", collect_video_files(os.path.join(tmp, "e.srt")) == [])
    check("存在しないパスは空", collect_video_files(os.path.join(tmp, "nil")) == [])
    check("上限定数が正", DROP_MAX_FILES >= 100)

    make_app()
    w = PlayerWindow()
    silence(w)
    w._resume = {}
    check("acceptDrops 有効", w.acceptDrops())

    # 1) 動画1本のドロップ = そのまま再生 (プレイリストは増えない)
    drop(w, [os.path.join(tmp, "a.mp4")])
    check("単一動画: 再生対象になる",
          w._current_path == os.path.abspath(os.path.join(tmp, "a.mp4")),
          str(w._current_path))
    check("単一動画: プレイリストは空のまま", w.playlist.count() == 0)
    w.player.pause()

    # 2) フォルダのドロップ = 中の動画を追加して先頭を再生
    ev = drop(w, [tmp])
    check("フォルダ: 2件追加される", w.playlist.count() == 2,
          str(w.playlist.count()))
    check("フォルダ: 先頭が再生される",
          w._current_path == os.path.abspath(os.path.join(tmp, "a.mp4")),
          str(w._current_path))
    check("フォルダ: 提案アクションを受理",
          ev.isAccepted() or ev.proposedAction() == Qt.DropAction.CopyAction)
    check("フォルダ: プレイリストが表示される", not w.pl_dock.isHidden())
    rows = [w.playlist.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(w.playlist.count())]
    check("フォルダ: 名前順で並ぶ",
          [os.path.basename(r) for r in rows] == ["a.mp4", "b.mp4"], f"{rows}")
    w.player.pause()

    # 3) 同じフォルダを再度 = 重複しない
    drop(w, [tmp])
    check("再ドロップ: 重複しない", w.playlist.count() == 2,
          str(w.playlist.count()))
    w.player.pause()

    # 4) 複数 URL (フォルダ + 単体動画) を同時に
    sub2 = os.path.join(sub, "z.mp4")
    shutil.copyfile(SAMPLE, sub2)
    drop(w, [tmp, sub2])
    check("混在: 新規 1 件のみ追加", w.playlist.count() == 3,
          str(w.playlist.count()))
    w.player.pause()

    # 5) 動画の無いフォルダ = 何も起きない
    empty = os.path.join(tmp, "empty")
    os.makedirs(empty, exist_ok=True)
    before = w.playlist.count()
    drop(w, [empty])
    check("空フォルダ: 変化なし", w.playlist.count() == before)

    # 6) .srt 単体のドロップ = 字幕として読み込む
    srt = os.path.join(tmp, "e.srt")
    drop(w, [srt])
    check("字幕ドロップ: 字幕パスが設定される",
          os.path.normpath(w._current_sub_path or "") == os.path.normpath(srt),
          str(w._current_sub_path))

    w.close()
    if os.path.isfile(RESUME):
        os.remove(RESUME)
    shutil.rmtree(tmp, ignore_errors=True)
    return finish("P18dnd")


if __name__ == "__main__":
    sys.exit(main())
