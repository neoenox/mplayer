"""P28: A-B リピート (区間リピート)。

- A / B / C キーと「再生」メニュー
- B 到達で A へ戻る (再生中のみ) / B の先へシークしても戻る
- 一時停止中は位置を勝手に戻さない
- 終端付近・終端 (EndOfMedia) でも止まらず A へ戻る
- A の打ち直しで B が解除 / C で全解除 / 欠損・未ロードで落ちない
- 別の動画を開くと解除 (ファイル単位の設定)
- ヘルプ・README の記載
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(BASE, "tmp_p28")
SESSION = os.path.join(TMP, "session.json")
RESUME = os.path.join(BASE, "resume.json")

os.makedirs(TMP, exist_ok=True)
os.environ["MPLAYER_SESSION_FILE"] = SESSION
if os.path.isfile(RESUME):
    os.remove(RESUME)

from helpers import (check, finish, make_app, patch_message_boxes, press_key,
                     silence, wait_until)

from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QMenu

from main import AB_MIN_GAP_MS, HELP_NOTES, SHORTCUTS, PlayerWindow

VIDEO = os.path.join(BASE, "test_60s.mp4")
VIDEO2 = os.path.join(BASE, "test_640x360.mp4")


def pump(ms=0):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def playing(w):
    return w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState


def settle(w, target, tol=600, timeout=4000):
    return wait_until(lambda: abs(w.player.position() - target) <= tol, timeout)


def main():
    patch_message_boxes()
    make_app()
    w = PlayerWindow()
    w.show()
    silence(w)
    w._resume = {}

    # --- 構造 (キー / メニュー / 表示) ---
    check("A キーが割当", w.ab_a_act.shortcut().toString() == "A",
          w.ab_a_act.shortcut().toString())
    check("B キーが割当", w.ab_b_act.shortcut().toString() == "B",
          w.ab_b_act.shortcut().toString())
    check("C キーが割当", w.ab_clear_act.shortcut().toString() == "C",
          w.ab_clear_act.shortcut().toString())
    check("A はウィンドウ全体で有効",
          w.ab_a_act.shortcutContext() == Qt.ShortcutContext.WindowShortcut,
          str(w.ab_a_act.shortcutContext()))
    check("B はウィンドウ全体で有効",
          w.ab_b_act.shortcutContext() == Qt.ShortcutContext.WindowShortcut,
          str(w.ab_b_act.shortcutContext()))
    check("C はウィンドウ全体で有効",
          w.ab_clear_act.shortcutContext() == Qt.ShortcutContext.WindowShortcut,
          str(w.ab_clear_act.shortcutContext()))
    menus = {m.title(): m for m in w.menuBar().findChildren(QMenu)}
    check("「再生」メニューがある", "再生" in menus, str(list(menus)))
    labels = [a.text() for a in menus["再生"].actions()] if "再生" in menus else []
    check("メニューに A/B/C の項目がある",
          len([x for x in labels if x.startswith("A-B")]) == 3, str(labels))
    check("最短区間は正の値", isinstance(AB_MIN_GAP_MS, int) and AB_MIN_GAP_MS > 0,
          str(AB_MIN_GAP_MS))
    check("初期状態は未設定", w.ab_state() == (None, None), str(w.ab_state()))
    check("初期状態はラベル非表示", not w.ab_label.isVisible())
    check("初期状態はループ無効", w.ab_active() is False)

    # --- 未ロード時 (落ちない) ---
    check("未ロードで A は設定できない", w.set_ab_a() is False)
    check("未ロードで B は設定できない", w.set_ab_b() is False)
    w.clear_ab()
    check("未ロードで解除しても落ちない", w.ab_state() == (None, None))

    # --- ロード ---
    check("動画をロード", w.load(VIDEO))
    check("長さを取得", wait_until(lambda: w.player.duration() > 0, 5000),
          str(w.player.duration()))
    dur = w.player.duration()
    check("長さは約60秒", 55000 <= dur <= 65000, str(dur))
    w.player.pause()

    # --- A 点 / B 点の設定 ---
    w.player.setPosition(1000)
    check("1秒へ移動", settle(w, 1000, 500), str(w.player.position()))
    check("A 点を設定できる", w.set_ab_a() is True)
    a1, b1 = w.ab_state()
    check("A 点が記録される", a1 is not None and abs(a1 - 1000) < 600, str(a1))
    check("B 点は未設定", b1 is None, str(b1))
    check("ラベルが表示される", w.ab_label.isVisible())
    check("ラベルに B 未設定を出す", "B 未設定" in w.ab_label.text(),
          w.ab_label.text())
    check("A と同じ位置の B は拒否", w.set_ab_b() is False)
    check("拒否時は B が入らない", w.ab_state()[1] is None)
    check("拒否時はループ無効", w.ab_active() is False)

    near = a1 + 100
    w.player.setPosition(near)
    settle(w, near, 400)
    check("最短区間未満の B は拒否", w.set_ab_b() is False)
    far = a1 + 2000
    w.player.setPosition(far)
    check("A の後に移動", settle(w, far, 600), str(w.player.position()))
    check("最短区間以上の B は受け付ける", w.set_ab_b() is True)
    a2, b2 = w.ab_state()
    check("A は据え置き", a2 == a1, f"{a2}")
    check("B が記録される", b2 is not None and b2 - a2 >= AB_MIN_GAP_MS, str(b2))
    check("区間が有効になる", w.ab_active() is True)
    check("ラベルにループを出す", "ループ" in w.ab_label.text(), w.ab_label.text())

    # --- 一時停止中は位置を勝手に戻さない ---
    w.player.setPosition(20000)
    pump(500)
    check("一時停止中は B を超えても戻らない", w.player.position() > 15000,
          str(w.player.position()))
    check("一時停止中でも設定は保持", w.ab_active() is True)

    # --- 再生中は B 到達で A へ戻る ---
    w.player.setPosition(a2 + 500)
    settle(w, a2 + 500, 400)
    w.player.play()
    check("再生が始まる", wait_until(lambda: playing(w), 3000))

    seen = {"max": 0}

    def track():
        seen["max"] = max(seen["max"], w.player.position())
        return w.player.position() < a2 + 300

    check("B 到達で A 側へ戻る", wait_until(track, 10000),
          f"max={seen['max']} pos={w.player.position()}")
    check("B の手前まで再生された", seen["max"] >= b2 - 1000, str(seen["max"]))
    check("戻っても再生は続く", playing(w))
    check("位置は A 付近", w.player.position() < a2 + 300, str(w.player.position()))

    # ループが繰り返し効き、B を大きく超えない
    over = 0
    for _ in range(20):
        pump(100)
        over = max(over, w.player.position())
    check("ループ中は B を大きく超えない", over < b2 + 1500, f"over={over} b={b2}")
    check("ループ後も再生中", playing(w))

    # --- 再生中に B の先へシークしても A 側へ戻る ---
    w.seek_by(60000)
    check("B の先へシークすると A 側へ戻る",
          wait_until(lambda: w.player.position() < a2 + 2000, 8000),
          str(w.player.position()))

    # --- 終端付近でも止まらない (EOS 経路) ---
    w.player.pause()
    w._ab_a, w._ab_b = 1000, dur  # 終端まで: EOS で止まらないことを見る
    check("終端までの区間が有効", w.ab_active() is True, str(w.ab_state()))
    w.player.setPosition(dur - 500)
    pump(100)
    w.player.play()
    check("終端付近でも A へ戻って続く",
          wait_until(lambda: w.player.position() < 2000, 10000),
          str(w.player.position()))
    check("終了扱いにならない", "終了" not in w.time_label.text(),
          w.time_label.text())

    # --- A の打ち直しで B が解除される ---
    w.player.pause()
    w.player.setPosition(9000)
    settle(w, 9000, 600)
    check("A を打ち直せる", w.set_ab_a() is True)
    check("打ち直しで B が解除される", w.ab_state()[1] is None, str(w.ab_state()))
    check("打ち直しでループ停止", w.ab_active() is False)
    check("ラベルは B 未設定に戻る", "B 未設定" in w.ab_label.text(),
          w.ab_label.text())

    # --- C キーで解除 / A・B キー (キー入力1回で1回だけ発火) ---
    # キーはアクティブなウィンドウにしか届かないため press_key を使う
    # (効かなかったときだけ押し直す。発火回数は別途検査する)。
    fired = {"a": 0, "b": 0, "c": 0}
    w.ab_a_act.triggered.connect(lambda: fired.__setitem__("a", fired["a"] + 1))
    w.ab_b_act.triggered.connect(lambda: fired.__setitem__("b", fired["b"] + 1))
    w.ab_clear_act.triggered.connect(lambda: fired.__setitem__("c", fired["c"] + 1))
    press_key(w, Qt.Key.Key_C, cond=lambda: w.ab_state() == (None, None))
    check("C キーで全解除", w.ab_state() == (None, None), str(w.ab_state()))
    check("C キーは1回だけ発火", fired["c"] == 1, str(fired["c"]))
    check("解除でラベルが消える", not w.ab_label.isVisible())
    check("解除でループ無効", w.ab_active() is False)

    w.player.setPosition(1000)
    settle(w, 1000, 500)
    press_key(w, Qt.Key.Key_A, cond=lambda: w.ab_state()[0] is not None)
    check("A キーで A 点が入る",
          fired["a"] == 1 and w.ab_state()[0] is not None, str(w.ab_state()))
    w.player.setPosition(4000)
    settle(w, 4000, 600)
    press_key(w, Qt.Key.Key_B, cond=lambda: w.ab_state()[1] is not None)
    check("B キーでループが始まる",
          fired["b"] == 1 and w.ab_state()[1] is not None, str(w.ab_state()))
    check("B キーは1回だけ発火", fired["b"] == 1, str(fired["b"]))
    press_key(w, Qt.Key.Key_C, cond=lambda: w.ab_state() == (None, None))
    check("C キーで再解除", w.ab_state() == (None, None), str(w.ab_state()))
    check("2回目の C も1回だけ発火", fired["c"] == 2, str(fired["c"]))
    press_key(w, Qt.Key.Key_C)
    check("未設定で C を押しても落ちない", w.ab_state() == (None, None))

    # --- 全画面でも設定できる ---
    w.toggle_fullscreen()
    pump(60)
    check("全画面へ入る", w._is_fullscreen is True)
    w.player.setPosition(1000)
    settle(w, 1000, 500)
    press_key(w, Qt.Key.Key_A, cond=lambda: w.ab_state()[0] is not None)
    w.player.setPosition(5000)
    settle(w, 5000, 600)
    press_key(w, Qt.Key.Key_B, cond=lambda: w.ab_state()[1] is not None)
    check("全画面でも A-B を設定できる", w.ab_active() is True, str(w.ab_state()))
    w.exit_fullscreen()
    pump(60)
    check("全画面を解除", w._is_fullscreen is False)

    # --- 別の動画を開くと解除 ---
    check("別の動画を開く", w.load(VIDEO2))
    check("ファイル切替で A-B が解除される", w.ab_state() == (None, None),
          str(w.ab_state()))
    check("ファイル切替でラベルも消える", not w.ab_label.isVisible())

    # --- ドキュメント / ヘルプ ---
    keys = [k for k, _ in SHORTCUTS]
    check("ヘルプに A / B を掲載", "A / B" in keys, str(keys))
    check("ヘルプに C を掲載", "C" in keys, str(keys))
    check("ヒントに A-B の説明がある",
          any("A-B" in n for n in HELP_NOTES), str(HELP_NOTES))

    readme = open(os.path.join(BASE, "README.md"), encoding="utf-8").read()
    check("README に A-B リピートの記載がある", "A-B リピート" in readme)
    check("README に解除 (C) の記載がある", "C" in readme and "解除" in readme)

    w.player.pause()
    w.close()
    if os.path.isfile(RESUME):
        os.remove(RESUME)
    if os.path.isfile(SESSION):
        os.remove(SESSION)
    shutil.rmtree(TMP, ignore_errors=True)
    return finish("P28abrepeat")


if __name__ == "__main__":
    sys.exit(main())
