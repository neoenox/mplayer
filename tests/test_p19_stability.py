"""P19: 長時間再生の安定性 (反復シーク・連続再生・ウィンドウ生成破棄・資源の伸び)。"""
import gc
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import (check, finish, handles_win, make_app, patch_message_boxes,
                     rss_mb_win, silence, skip, wait_until)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from main import PlayerWindow

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHORT = os.path.join(BASE, "test_640x360.mp4")
OTHER = os.path.join(BASE, "test_silent.mp4")
LONG = os.path.join(BASE, "test_60s.mp4")
RESUME = os.path.join(BASE, "resume.json")


def pump(ms=0):
    from PySide6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main():
    patch_message_boxes()
    make_app()

    # ---------- A. ウィンドウ生成/破棄の反復 (リーク検出) ----------
    for _ in range(3):  # ウォームアップ
        w = PlayerWindow()
        w.close()
        w.deleteLater()
    pump(50)
    gc.collect()
    base_widgets = len(QApplication.topLevelWidgets())
    h0, r0 = handles_win(), rss_mb_win()

    for _ in range(15):
        w = PlayerWindow()
        silence(w)
        w.close()
        w.deleteLater()
        pump(10)
    gc.collect()
    pump(100)
    after_widgets = len(QApplication.topLevelWidgets())
    h1, r1 = handles_win(), rss_mb_win()

    check("反復後もトップレベルウィジェットが増えない",
          after_widgets <= base_widgets + 2,
          f"{base_widgets} -> {after_widgets}")
    if h1 > 0 and h0 > 0:
        check("反復後もハンドル増加が小さい", (h1 - h0) <= 60,
              f"{h0} -> {h1} (+{h1 - h0})")
    else:
        skip("ハンドル計測", "API利用不可")
    if r1 > 0 and r0 > 0:
        check("反復後もRSS増加が小さい", (r1 - r0) <= 120,
              f"{r0:.0f}MB -> {r1:.0f}MB (+{r1 - r0:.0f})")
    else:
        skip("RSS計測", "API利用不可")

    # ---------- B. 同一ファイルの繰り返しオープン ----------
    w = PlayerWindow()
    silence(w)
    w._resume = {}
    ok = True
    gens = []
    for i in range(12):
        if not w.load(SHORT):
            ok = False
            break
        gens.append(w._media_gen)
        w.player.pause()
        pump(20)
    check("同一ファイルを12回開ける", ok)
    check("オープンごとに世代が進む", len(set(gens)) == len(gens),
          f"{len(set(gens))}/{len(gens)}")
    check("オープン後もパスが正しい",
          w._current_path == os.path.abspath(SHORT), str(w._current_path))
    check("オープン後もタイトルにファイル名",
          os.path.basename(SHORT) in w.windowTitle())
    check("オープン後も字幕はリセット", w._current_sub_path is None)

    # ---------- C. シーク連打 ----------
    w.load(LONG)
    silence(w)
    check("長尺の長さを取得", wait_until(lambda: w.player.duration() > 50000, 8000),
          str(w.player.duration()))
    dur = w.player.duration()
    deltas = [1000, -1000, 5000, -5000, 10000, -10000, 250, -250, 30000, -30000]
    for i in range(50):
        w.seek_by(deltas[i % len(deltas)])
        pump(0)
    pump(200)
    pos = w.player.position()
    check("シーク連打後も位置が範囲内", 0 <= pos <= dur, f"pos={pos} dur={dur}")
    check("シーク連打後もエラーでない",
          w.player.error().name == "NoError", w.player.error().name)
    check("シーク連打後も再生継続 (位置が進む)",
          wait_until(lambda: w.player.position() > pos + 100, 6000),
          f"{pos} -> {w.player.position()}")
    # 端への張り付き (0/末尾) を跨いでも破綻しない
    for target in (0, dur, 0, dur, dur // 2):
        w.seek.setValue(target)
        w._post_seek(target)
        pump(0)
    pump(150)
    check("端シーク後も位置が範囲内",
          0 <= w.player.position() <= dur, str(w.player.position()))
    w.player.pause()

    # ---------- D. 連続再生 (EOS→自動送り) の反復 ----------
    w.clear_playlist()
    w.add_to_playlist([SHORT, OTHER])
    check("2件のプレイリストを用意", w.playlist.count() == 2,
          str(w.playlist.count()))
    advances = 0
    for cycle in range(3):
        if not w.play_index(0):
            break
        pump(200)
        d = w.player.duration()
        if d > 1500:
            # 終端付近へ飛ばして EOS を早める
            w._post_seek(max(0, d - 900))
        if wait_until(lambda: w.playlist.currentRow() == 1, 8000):
            advances += 1
        pump(100)
    check("EOS で次の動画へ自動送り (3回)", advances == 3, f"{advances}/3")
    check("自動送り後もエラーでない",
          w.player.error().name == "NoError", w.player.error().name)
    check("自動送り後もプレイリスト件数は不変", w.playlist.count() == 2)
    w.player.pause()

    # ---------- E. 字幕表示の反復切替 ----------
    import tempfile
    tdir = tempfile.mkdtemp(prefix="mplayer_p19_")
    srt = os.path.join(tdir, "sub.srt")
    with open(srt, "w", encoding="utf-8") as f:
        f.write("1\n00:00:00,500 --> 00:00:04,000\nこんにちは\n\n"
                "2\n00:00:04,500 --> 00:00:09,000\nテスト字幕\n")
    w.load(LONG)
    silence(w)
    pump(100)
    subs_ok = True
    w.load_subtitles(srt)
    for i in range(30):
        try:
            w.subs_btn.setChecked(i % 2 == 0)
            w.set_subtitle_size((14, 18, 26)[i % 3])
            w.set_subtitle_outline(i % 2 == 0)
            w.set_subtitle_pos(("bottom", "middle", "top")[i % 3])
        except Exception:
            subs_ok = False
            break
    pump(150)
    check("字幕表示の反復切替で例外なし", subs_ok)
    check("字幕切替後も字幕パス保持",
          os.path.normpath(w._current_sub_path or "") == os.path.normpath(srt),
          str(w._current_sub_path))
    check("字幕切替後もエラーでない",
          w.player.error().name == "NoError", w.player.error().name)
    w.player.pause()
    import shutil
    shutil.rmtree(tdir, ignore_errors=True)

    # ---------- F. 全画面の反復切替 ----------
    fs_ok = True
    for i in range(10):
        try:
            w.toggle_fullscreen()
        except Exception:
            fs_ok = False
            break
        pump(0)
    check("全画面の反復切替で例外なし", fs_ok)
    check("偶数回で全画面解除に戻る", not w.isFullScreen(), str(w.isFullScreen()))
    check("解除後はメニューバー表示", not w.menuBar().isHidden())
    check("解除後もウィンドウは表示中", w.isVisible() or not w.isHidden())
    w.player.pause()

    # ---------- 最終確認 ----------
    w.load(SHORT)
    silence(w)
    check("総仕上げ: まだ再生できる",
          wait_until(lambda: w.player.duration() > 1000, 8000),
          str(w.player.duration()))
    check("総仕上げ: エラーなし",
          w.player.error().name == "NoError", w.player.error().name)
    w.close()
    pump(50)
    gc.collect()

    if os.path.isfile(RESUME):
        os.remove(RESUME)
    return finish("P19stability")


if __name__ == "__main__":
    sys.exit(main())
