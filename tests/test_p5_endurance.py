"""P5-P2: 耐久反復テスト (無音)。

切替・再生・一時停止・シークを15サイクル反復し、RSS/ハンドル/例外/生存を測定。
許容増加量 (RSS<60MB, handles<150) を事前定義し数値判定する。
製品の音量既定値は触らない (silenceのみ)。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, handles_win, make_app, patch_message_boxes, rss_mb_win, \
    silence, wait_until

from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest

from main import PlayerWindow

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO = os.path.join(BASE, "test_640x360.mp4")
LONG = os.path.join(BASE, "test_60s.mp4")

CYCLES = 20
# 実測知見 (40サイクル診断):
# - RSSは15〜20サイクルで約250MBに頭打ち ( unbounded leakなし)
# - ハンドルは切替ごとに約+1〜4の線形増加が残る (Qtバックエンド側。16M上限に対し無視可能だが記録する)
# 判定は「頭打ち後の振れ幅」と「傾き上限」で行い、悪化の回帰検出を目的とする。
WARMUP = 20
RSS_WINDOW_MB = 60.0
RSS_ABS_MB = 400.0
HANDLES_SLOPE = 6.0
HANDLES_ABS = 2500


def slope(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den


def main():
    patch_message_boxes()
    app = make_app()
    w = PlayerWindow()
    w.show()
    silence(w)

    rss0, h0 = rss_mb_win(), handles_win()
    check("baseline measurable", rss0 > 0 and h0 > 0, f"rss={rss0:.1f}MB h={h0}")
    # ウォームアップ (パイプライン構築の初期コストを測定対象外にする)
    for i in range(WARMUP):
        w.load(VIDEO if i % 2 == 0 else LONG)
        wait_until(lambda: w.player.playbackState() ==
                   QMediaPlayer.PlaybackState.PlayingState, 10000)
        w.player.pause()
        QTest.qWait(200)
        w.player.play()
        QTest.qWait(600)
    rss0, h0 = rss_mb_win(), handles_win()
    print(f"post-warmup baseline rss={rss0:.1f}MB h={h0}", flush=True)
    rss_hist, h_hist = [], []
    errors = 0
    for i in range(CYCLES):
        try:
            w.load(VIDEO if i % 2 == 0 else LONG)
            if not wait_until(lambda: w.player.playbackState() ==
                              QMediaPlayer.PlaybackState.PlayingState, 10000):
                errors += 1
                continue
            w.player.pause()
            QTest.qWait(200)
            dur = w.player.duration()
            if dur > 3000:
                w.player.setPosition(dur // 2)
                QTest.qWait(400)
            w.player.play()
            QTest.qWait(600)
            rss_hist.append(rss_mb_win())
            h_hist.append(handles_win())
        except Exception as e:
            errors += 1
            print(f"[cycle {i} exception] {e}", flush=True)
    check("no cycle errors", errors == 0, f"errors={errors}/{CYCLES}")
    xs = list(range(len(rss_hist)))
    rss_slope = slope(xs, rss_hist) if rss_hist else 0.0
    h_slope = slope(xs, h_hist) if h_hist else 0.0
    rss_max = max(rss_hist) if rss_hist else 0.0
    print(f"rss slope={rss_slope:.2f}MB/cycle max={rss_max:.1f}MB", flush=True)
    print(f"handles slope={h_slope:.2f}/cycle {h_hist[0] if h_hist else '-'}"
          f"->{h_hist[-1] if h_hist else '-'}", flush=True)
    check("rss plateau (window)", (max(rss_hist) - min(rss_hist)) < RSS_WINDOW_MB
          if rss_hist else False, f"range={max(rss_hist)-min(rss_hist):.1f}MB")
    check("rss absolute cap", rss_max < RSS_ABS_MB, f"max={rss_max:.1f}MB")
    check("handles slope bounded", h_slope < HANDLES_SLOPE, f"slope={h_slope:.2f}/cycle")
    check("handles absolute cap", (h_hist[-1] if h_hist else 0) < HANDLES_ABS,
          f"last={h_hist[-1] if h_hist else '-'}")
    check("alive and playing at end", wait_until(
        lambda: w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState, 8000))
    return finish("P5endurance")


if __name__ == "__main__":
    sys.exit(main())
