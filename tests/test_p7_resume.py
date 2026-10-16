"""P7: 前回再生位置の記憶・復元 (無音・実イベント)。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, patch_message_boxes, silence, wait_until

from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest

import main as app_module
from main import PlayerWindow

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LONG = os.path.join(BASE, "test_60s.mp4")
RESUME = os.path.join(BASE, "resume.json")


def main():
    patch_message_boxes()
    app = make_app()
    if os.path.isfile(RESUME):
        os.remove(RESUME)

    w = PlayerWindow()
    w.show()
    silence(w)
    w.load(LONG)
    check("playing", wait_until(
        lambda: w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState, 10000))
    w.player.setPosition(30000)
    QTest.qWait(800)
    w.toggle_play()  # 一時停止=記憶
    QTest.qWait(500)
    check("paused", w.player.playbackState() == QMediaPlayer.PlaybackState.PausedState)
    saved = {}
    try:
        with open(RESUME, encoding="utf-8") as f:
            saved = json.load(f)
    except Exception as e:
        check("resume file written", False, str(e))
    got = saved.get(os.path.abspath(LONG), {}).get("pos", -1)
    check("position remembered", 25000 <= got <= 35000, f"pos={got}")

    # 別窓=再起動相当で復元される
    w2 = PlayerWindow()
    w2.show()
    silence(w2)
    w2.load(LONG)
    check("resumed near 30000", wait_until(lambda: 25000 <= w2.player.position() <= 35000, 12000),
          f"pos={w2.player.position()}")

    # 明示停止で記憶消去→次回は先頭
    w2.stop()
    QTest.qWait(800)
    try:
        with open(RESUME, encoding="utf-8") as f:
            saved2 = json.load(f)
    except Exception:
        saved2 = {}
    check("stop forgets", os.path.abspath(LONG) not in saved2)
    w3 = PlayerWindow()
    w3.show()
    silence(w3)
    w3.load(LONG)
    QTest.qWait(2500)
    check("starts from 0 after stop", w3.player.position() < 8000, f"pos={w3.player.position()}")

    # 範囲外・破損時は先頭から・クラッシュなし
    with open(RESUME, "w", encoding="utf-8") as f:
        json.dump({os.path.abspath(LONG): {"pos": 999999999}}, f)
    w4 = PlayerWindow()
    w4.show()
    silence(w4)
    w4.load(LONG)
    QTest.qWait(2500)
    check("out-of-range ignored", w4.player.position() < 8000, f"pos={w4.player.position()}")
    with open(RESUME, "w", encoding="utf-8") as f:
        f.write("{broken json,,,")
    try:
        w5 = PlayerWindow()
        check("corrupt json no crash", True)
        w5.deleteLater()
    except Exception as e:
        check("corrupt json no crash", False, str(e))

    # 上限100件
    w6 = PlayerWindow()
    for i in range(105):
        w6._resume[f"C:\\fake\\v{i}.mp4"] = {"pos": 10000 + i}
    w6._save_resume()
    with open(RESUME, encoding="utf-8") as f:
        n = len(json.load(f))
    check("capped at 100", n <= 100, f"n={n}")
    w6.deleteLater()

    if os.path.isfile(RESUME):
        os.remove(RESUME)
    return finish("P7resume")


if __name__ == "__main__":
    sys.exit(main())
