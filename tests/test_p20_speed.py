"""P20: 再生速度のキーボード操作 (] で上げる / [ で下げる)。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import (check, finish, make_app, patch_message_boxes, silence,
                     wait_until)

from PySide6.QtCore import Qt

from main import SHORTCUTS, PlayerWindow, build_help_html

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO = os.path.join(BASE, "test_640x360.mp4")
RESUME = os.path.join(BASE, "resume.json")


def main():
    patch_message_boxes()
    make_app()
    w = PlayerWindow()
    silence(w)
    w._resume = {}
    w.load(VIDEO)
    wait_until(lambda: w.player.duration() > 1000, 8000)

    check("速度リスト", w._rates == [0.5, 1.0, 1.5, 2.0], f"{w._rates}")
    check("既定は 1.0x", w._rates[w._rate_idx] == 1.0, str(w._rates[w._rate_idx]))

    check("ショートカット ] が登録",
          w.speed_up_act.shortcut().toString() == "]",
          w.speed_up_act.shortcut().toString())
    check("ショートカット [ が登録",
          w.speed_down_act.shortcut().toString() == "[",
          w.speed_down_act.shortcut().toString())

    w.speed_up_act.trigger()
    check("] で 1.5x", abs(w.player.playbackRate() - 1.5) < 0.01,
          str(w.player.playbackRate()))
    check("] でボタン表示も更新", "1.5" in w.speed_btn.text(), w.speed_btn.text())
    w.speed_up_act.trigger()
    check("] で 2.0x", abs(w.player.playbackRate() - 2.0) < 0.01,
          str(w.player.playbackRate()))
    w.speed_up_act.trigger()
    check("上限 2.0x で据え置き", abs(w.player.playbackRate() - 2.0) < 0.01,
          str(w.player.playbackRate()))

    w.speed_down_act.trigger()
    check("[ で 1.5x", abs(w.player.playbackRate() - 1.5) < 0.01,
          str(w.player.playbackRate()))
    w.speed_down_act.trigger()
    w.speed_down_act.trigger()
    check("[ で 0.5x", abs(w.player.playbackRate() - 0.5) < 0.01,
          str(w.player.playbackRate()))
    w.speed_down_act.trigger()
    check("下限 0.5x で据え置き", abs(w.player.playbackRate() - 0.5) < 0.01,
          str(w.player.playbackRate()))

    # ボタン (サイクル) と共存する
    w._rate_idx = 3  # 2.0x
    w.cycle_speed()
    check("サイクルは 2.0→0.5 へ回り込む",
          abs(w.player.playbackRate() - 0.5) < 0.01, str(w.player.playbackRate()))

    # 再生自体は継続する
    w._apply_rate()  # 0.5x のまま
    check("速度変更後もエラーでない", w.player.error().name == "NoError",
          w.player.error().name)

    check("ヘルプに ] / [ を掲載",
          any(k == "] / [" for k, _ in SHORTCUTS), f"{SHORTCUTS}")
    check("ヘルプHTMLに ] / [ を掲載", "] / [" in build_help_html())

    w.player.pause()
    w.close()
    if os.path.isfile(RESUME):
        os.remove(RESUME)
    return finish("P20speed")


if __name__ == "__main__":
    sys.exit(main())
