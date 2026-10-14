"""P2: 異常系・耐久性 (クラッシュ/フリーズ/リーク監視)。"""
import os
import random
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, dialog_calls, finish, handles_win, make_app, patch_message_boxes, \
    rss_mb_win, silence, skip, wait_until

from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest

from main import PlayerWindow

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO = os.path.join(BASE, "test_640x360.mp4")
LONG = os.path.join(BASE, "test_60s.mp4")
TMP = os.path.join(BASE, "tmp_p2")


def rss_mb():
    return rss_mb_win()


def handles():
    return handles_win()


def main():
    patch_message_boxes()
    app = make_app()
    os.makedirs(TMP, exist_ok=True)
    w = PlayerWindow()
    w.show()
    silence(w)  # 検証中は無音

    # --- 1. 存在しないファイル ---
    r = w.load(os.path.join(BASE, "no_such_file.mp4"))
    check("missing file returns False", r is False)
    QTest.qWait(400)

    # --- 2. 0バイト ---
    zero = os.path.join(TMP, "empty.mp4")
    open(zero, "wb").close()
    try:
        w.load(zero)
        QTest.qWait(1500)
        check("0-byte no crash", True)
    except Exception as e:
        check("0-byte no crash", False, str(e))

    # --- 3. 途中で切れたMP4 (先頭40KBのみ) ---
    cut = os.path.join(TMP, "cut.mp4")
    with open(VIDEO, "rb") as f, open(cut, "wb") as g:
        g.write(f.read(40000))
    try:
        w.load(cut)
        QTest.qWait(1500)
        check("truncated mp4 no crash", True)
    except Exception as e:
        check("truncated mp4 no crash", False, str(e))

    # --- 4. 非対応形式 ---
    txt = os.path.join(TMP, "note.mp4")
    with open(txt, "w", encoding="utf-8") as f:
        f.write("これは動画ではありません\n" * 50)
    try:
        w.load(txt)
        QTest.qWait(1500)
        check("unsupported no crash", True)
    except Exception as e:
        check("unsupported no crash", False, str(e))
    check("error dialog shown for bad files", len(dialog_calls) >= 1,
          f"dialogs={len(dialog_calls)}")

    # --- 5. 日本語・空白パス ---
    uni = os.path.join(TMP, "テスト 動画 .mp4")
    shutil.copy(VIDEO, uni)
    w.load(uni)
    check("unicode/space path plays", wait_until(
        lambda: w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState, 10000),
        uni)

    # --- 6. 連続シーク20回 ---
    w.load(VIDEO)
    wait_until(lambda: w.player.duration() > 4000, 10000)
    w.player.pause()
    QTest.qWait(300)
    rnd = random.Random(42)
    try:
        for _ in range(20):
            w.player.setPosition(rnd.randint(0, 4900))
            QTest.qWait(150)
        QTest.qWait(800)
        pos = w.player.position()
        check("20 rapid seeks survive", 0 <= pos <= 5000, f"pos={pos}")
    except Exception as e:
        check("20 rapid seeks survive", False, str(e))

    # --- 7. 再生・停止50回 + リソース監視 (アプリのstop経路を使用) ---
    w.load(VIDEO)
    wait_until(lambda: w.player.duration() > 0, 10000)
    rss0, h0 = rss_mb(), handles()
    try:
        for i in range(50):
            w.player.play()
            QTest.qWait(120)
            w.stop()
            QTest.qWait(150)
        rss1, h1 = rss_mb(), handles()
        check("50 play/stop no crash", True)
        if rss0 < 0 or rss1 < 0:
            skip("rss monitoring (Windows API unavailable)")
        else:
            check("rss growth < 80MB", (rss1 - rss0) < 80, f"{rss0:.1f}->{rss1:.1f}MB")
        if h0 < 0 or h1 < 0:
            skip("handles monitoring (Windows API unavailable)")
        else:
            check("handles growth < 200", (h1 - h0) < 200, f"{h0}->{h1}")
    except Exception as e:
        check("50 play/stop no crash", False, str(e))

    # --- 8. 連続切替10回 ---
    try:
        for i in range(10):
            w.load(VIDEO if i % 2 == 0 else LONG)
            QTest.qWait(500)
        check("10 file switches survive", wait_until(
            lambda: w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState, 8000))
    except Exception as e:
        check("10 file switches survive", False, str(e))

    # --- 9. 長尺 sustained 再生 (~25秒、単調増加+フリーズなし) ---
    w.load(LONG)
    check("long video duration ~60s", wait_until(lambda: w.player.duration() > 55000, 12000),
          f"dur={w.player.duration()}")
    samples = []
    try:
        for _ in range(5):
            QTest.qWait(5000)
            samples.append(w.player.position())
        mono = all(b > a for a, b in zip(samples, samples[1:]))
        check("position advances monotonically 25s", mono, f"samples={samples}")
        check("no freeze (last>20s)", samples[-1] > 20000, f"last={samples[-1]}")
        w.player.setPosition(30000)
        QTest.qWait(1500)
        check("mid-play seek ok", abs(w.player.position() - 30000) < 5000,
              f"pos={w.player.position()}")
    except Exception as e:
        check("sustained playback", False, str(e))

    shutil.rmtree(TMP, ignore_errors=True)
    return finish("P2")


if __name__ == "__main__":
    sys.exit(main())
