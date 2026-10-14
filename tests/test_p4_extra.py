"""P4追加: プラグイン同梱・再生中削除・長いパス・既定音量の検証 (無音)。"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, handles_win, make_app, patch_message_boxes, silence, skip, \
    wait_until

from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest

import PySide6
from main import PlayerWindow

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO = os.path.join(BASE, "test_640x360.mp4")
TMP = os.path.join(BASE, "tmp_p4")


def main():
    patch_message_boxes()
    app = make_app()
    os.makedirs(TMP, exist_ok=True)

    # --- 1. 実行中のPySide6に必須プラグイン/DLLが同梱 ---
    root = os.path.dirname(PySide6.__file__)
    plug = os.path.join(root, "plugins", "multimedia", "ffmpegmediaplugin.dll")
    check("ffmpeg plugin bundled", os.path.isfile(plug), plug)
    missing = [d for d in ("avcodec-63.dll", "avformat-63.dll", "avutil-61.dll")
               if not os.path.isfile(os.path.join(root, d))]
    check("ffmpeg dlls bundled", not missing, f"missing={missing}")

    w = PlayerWindow()
    w.show()
    silence(w)

    # --- 2. 製品既定の音量は80・非ミュート (テストが変えていないこと) ---
    # silence()はvolスライダーを0にする= audio 0.0。既定確認は新規窓で。
    w0 = PlayerWindow()
    check("default volume 0.8", abs(w0.audio.volume() - 0.8) < 1e-6, f"vol={w0.audio.volume()}")
    check("default unmuted", not w0.audio.isMuted())
    w0.deleteLater()

    # --- 3. 停止後にファイルを削除→存在しないファイルを開く→別ファイル再生 ---
    # (Windowsは再生中のファイルをロックするため、消失は停止後に検証する)
    victim = os.path.join(TMP, "victim.mp4")
    shutil.copy(VIDEO, victim)
    w.load(victim)
    check("victim playing", wait_until(
        lambda: w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState, 10000))
    QTest.qWait(1000)
    # 再生中はOSロックで削除不可のはず (ロック保持の積極検証)
    try:
        os.remove(victim)
        check("locked while playing", False, "deleted despite playing (unexpected)")
        shutil.copy(VIDEO, victim)
    except PermissionError:
        check("locked while playing", True)
    except OSError as e:
        check("locked while playing", False, str(e))
    w.stop()  # アプリの停止経路 (pause+rewind)。
    QTest.qWait(800)
    # 別ファイルを読み込むと旧ソースが外れてロックが解放される
    w.load(VIDEO)
    check("switched file playing", wait_until(
        lambda: w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState, 10000))
    QTest.qWait(800)
    try:
        os.remove(victim)
        check("lock released after switch", True)
    except OSError as e:
        check("lock released after switch", False, str(e))
    r = w.load(victim)
    check("open deleted file returns False", r is False)
    QTest.qWait(500)
    w.load(VIDEO)
    check("plays another file after deletion", wait_until(
        lambda: w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState, 10000))

    # --- 4. 長いパス (~200文字) ---
    deep = TMP
    while len(deep) < 180:
        deep = os.path.join(deep, "subdir_123456789")
    os.makedirs(deep, exist_ok=True)
    longp = os.path.join(deep, "longname_video.mp4")
    shutil.copy(VIDEO, longp)
    w.load(longp)
    check("long path plays", wait_until(
        lambda: w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState, 10000),
        f"len={len(longp)}")

    # --- 5. 連続オープンのハンドル安定 (Windows API計測・追加依存なし) ---
    try:
        h0 = handles_win()
        for i in range(10):
            w.load(VIDEO if i % 2 == 0 else longp)
            QTest.qWait(400)
        h1 = handles_win()
        if h0 < 0 or h1 < 0:
            skip("handles check (Windows API unavailable)")
        else:
            check("handles stable over 10 opens", (h1 - h0) < 100, f"{h0}->{h1}")
    except Exception as e:
        check("handles stable over 10 opens", False, str(e))

    shutil.rmtree(TMP, ignore_errors=True)
    return finish("P4extra")


if __name__ == "__main__":
    sys.exit(main())
