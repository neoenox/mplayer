"""P5-P0: 遅延シーク/EOSの競合検証 (無音)。

- 予約シーク直後のファイル切替で旧ターゲットが新ファイルへ誤適用されない
- 連続ドラッグは最後だけが適用される
- EOS直後の切替で旧EOS処理が新ファイルを巻き戻さない
- 5秒動画の自然終了で先頭戻し+終了表示になる
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, patch_message_boxes, silence, wait_until

from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest

from main import PlayerWindow

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(BASE, "test_640x360.mp4")   # 5秒
B = os.path.join(BASE, "test_60s.mp4")       # 60秒


def main():
    patch_message_boxes()
    app = make_app()
    w = PlayerWindow()
    w.show()
    silence(w)

    # --- 1. 予約シーク→即切替: 旧ターゲットがBへ漏れない ---
    w.load(A)
    check("A duration", wait_until(lambda: w.player.duration() > 4000, 10000))
    w.player.pause()
    QTest.qWait(300)
    w.seek.setValue(4400)
    w.seek_released()          # 遅延シークを予約 (まだ実行されない)
    w.load(B)                  # 同一ディスパッチ内で切替 (競合を確定的に再現)
    QTest.qWait(2000)
    pos = w.player.position()
    check("stale seek dropped after switch", pos < 2000, f"pos={pos} (4400なら漏洩)")
    check("B playing", w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)

    # --- 1b. ガード陰性対照: 旧世代の適用は無視される ---
    w._apply_seek(w._media_gen - 1, 59000)
    QTest.qWait(800)
    check("stale gen ignored", w.player.position() < 59000 - 5000,
          f"pos={w.player.position()}")

    # --- 2. 連続ドラッグは最後だけ適用 ---
    w.load(A)
    wait_until(lambda: w.player.duration() > 4000, 10000)
    w.player.pause()
    QTest.qWait(300)
    for v in (1000, 2000, 3000, 4500):
        w.seek.setValue(v)
        w.seek_released()
    QTest.qWait(1500)
    pos = w.player.position()
    check("last drag wins", abs(pos - 4500) < 1500, f"pos={pos}")

    # --- 3. EOS直後の切替で旧EOS処理がBを巻き戻さない ---
    w.load(A)
    wait_until(lambda: w.player.duration() > 4000, 10000)
    w.player.setPosition(4800)  # 終端付近へ
    QTest.qWait(1200)           # EOS発火を待つ (5秒動画)
    w.load(B)                   # EOS処理と競合させる
    QTest.qWait(2500)
    pos = w.player.position()
    st = w.player.playbackState()
    check("B not rewound by stale EOS", pos > 500 or st == QMediaPlayer.PlaybackState.PlayingState,
          f"pos={pos} state={st}")

    # --- 4. 自然終了: 先頭戻し+終了表示 ---
    w.load(A)
    wait_until(lambda: w.player.duration() > 4000, 10000)
    w.player.setPosition(4500)
    ok = wait_until(lambda: "(終了)" in w.time_label.text(), 15000)
    check("EOS label", ok, f"label={w.time_label.text()}")
    check("EOS rewound", w.player.position() == 0, f"pos={w.player.position()}")
    check("EOS paused", w.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState)

    # --- 5. 予約シーク直後の終了 (別プロセス・ハング検出付き) ---
    import subprocess
    exe = sys.executable
    try:
        cp = subprocess.run([exe, "-u", os.path.join(BASE, "tests", "close_seek_check.py")],
                            cwd=BASE, capture_output=True, text=True, timeout=30,
                            errors="replace")
        check("quit with pending seek exits cleanly", cp.returncode == 0,
              f"exit={cp.returncode}")
    except subprocess.TimeoutExpired:
        check("quit with pending seek exits cleanly", False, "timeout (quit hang)")
    except Exception as e:
        check("quit with pending seek exits cleanly", False, str(e))

    return finish("P5race")


if __name__ == "__main__":
    sys.exit(main())
