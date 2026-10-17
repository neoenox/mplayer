"""P26: ← / → キーで 5秒戻し / 5秒送り (clamp・累積・全画面・ドキュメント整合)。"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(BASE, "tmp_p26")
SESSION = os.path.join(TMP, "session.json")
RESUME = os.path.join(BASE, "resume.json")

os.makedirs(TMP, exist_ok=True)
os.environ["MPLAYER_SESSION_FILE"] = SESSION
if os.path.isfile(RESUME):
    os.remove(RESUME)

from helpers import check, finish, make_app, patch_message_boxes, silence, wait_until

from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtGui import QKeySequence

from main import SHORTCUTS, PlayerWindow

VIDEO = os.path.join(BASE, "test_60s.mp4")


def pump(ms=0):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def find_action(w, key):
    seq = QKeySequence(key)
    for a in w.actions():
        if a.shortcut() == seq:
            return a
    return None


def settle(w, target, tol=1200, timeout=4000):
    return wait_until(lambda: abs(w.player.position() - target) <= tol, timeout)


def at(w, target, tol=1200):
    return abs(w.player.position() - target) <= tol


def main():
    patch_message_boxes()
    app = make_app()
    w = PlayerWindow()
    silence(w)
    w._resume = {}

    right = find_action(w, Qt.Key.Key_Right)
    left = find_action(w, Qt.Key.Key_Left)
    check("→ のアクションがある", right is not None)
    check("← のアクションがある", left is not None)
    check("→ はウィンドウ全体で有効",
          right.shortcutContext() == Qt.ShortcutContext.WindowShortcut,
          str(right.shortcutContext()))
    check("← はウィンドウ全体で有効",
          left.shortcutContext() == Qt.ShortcutContext.WindowShortcut,
          str(left.shortcutContext()))
    check("シークバーはフォーカスを取らない",
          w.seek.focusPolicy() == Qt.FocusPolicy.NoFocus,
          str(w.seek.focusPolicy()))
    check("ヘルプ表記も 5秒", ("← / →", "5秒戻る / 5秒進む") in SHORTCUTS,
          str([s for s in SHORTCUTS if s[0] == "← / →"]))

    # 動画なしでも落ちない
    w.seek_by(5000)
    check("未ロード時は何もしない", w.seek.value() == 0, str(w.seek.value()))
    right.trigger()
    pump(20)
    check("未ロードで → を押しても落ちない", w.player.position() == 0,
          str(w.player.position()))

    # ロードして位置を固定
    check("動画をロード", w.load(VIDEO))
    check("長さを取得", wait_until(lambda: w.player.duration() > 0, 5000),
          str(w.player.duration()))
    dur = w.player.duration()
    check("長さは約60秒", 55000 <= dur <= 65000, str(dur))
    w.player.pause()
    w.player.setPosition(0)
    check("先頭へ移動", settle(w, 0, 300), str(w.player.position()))

    # → で 5秒送り
    right.trigger()
    check("→ で 5秒送り", settle(w, 5000), str(w.player.position()))

    # 連続押しで累積
    right.trigger()
    check("→ 2回で約10秒", settle(w, 10000), str(w.player.position()))

    # ← で戻る
    left.trigger()
    check("← で 5秒戻し", settle(w, 5000), str(w.player.position()))
    left.trigger()
    check("← 2回で先頭付近", settle(w, 0), str(w.player.position()))

    # 先頭でさらに戻ってもマイナスにならない
    left.trigger()
    pump(150)
    check("先頭より前に戻らない", w.player.position() >= 0 and at(w, 0, 500),
          str(w.player.position()))

    # 末尾クランプ
    w.seek_by(600000)
    check("大きく送ると末尾で止まる", settle(w, dur, 800),
          f"{w.player.position()} / {dur}")
    right.trigger()
    pump(150)
    check("末尾で → を押しても末尾のまま", at(w, dur, 800),
          f"{w.player.position()} / {dur}")

    # 直接 seek_by の整合
    w.player.setPosition(0)
    settle(w, 0, 300)
    check("seek_by(+5000) が効く", (w.seek_by(5000) is None) and settle(w, 5000),
          str(w.player.position()))
    check("seek_by(-5000) が効く", (w.seek_by(-5000) is None) and settle(w, 0),
          str(w.player.position()))

    # 全画面でも効く
    w.toggle_fullscreen()
    pump(30)
    check("全画面へ入る", w._is_fullscreen is True)
    w.player.setPosition(10000)
    settle(w, 10000, 500)
    right.trigger()
    check("全画面でも 5秒送りが効く", settle(w, 15000), str(w.player.position()))
    w.exit_fullscreen()
    pump(30)
    check("全画面を解除", w._is_fullscreen is False)

    # ドキュメント整合 (古い「1秒」表記が残っていない)
    with open(os.path.join(BASE, "README.md"), encoding="utf-8") as f:
        readme = f.read()
    check("README に 5秒送りの記載がある", "5秒送り" in readme)
    check("README の古い '1秒' 表記が消えている",
          "矢印キーで1秒" not in readme)

    w.player.pause()
    w.close()
    if os.path.isfile(RESUME):
        os.remove(RESUME)
    if os.path.isfile(SESSION):
        os.remove(SESSION)
    shutil.rmtree(TMP, ignore_errors=True)
    return finish("P26seekkeys")


if __name__ == "__main__":
    sys.exit(main())
