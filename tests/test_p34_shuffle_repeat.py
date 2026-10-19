"""P34: プレイリストのシャッフル再生とリピート (なし / 1 本 / 全曲)。

- Shift+S / Shift+R とリスト下のボタン / メニューから切り替える
- シャッフル順はパスで持つので、追加・削除・並べ替えに追従する
- リピートは曲の終わり (EOS) の振る舞いで確かめる
- 値は session.json に保存し次回起動時に復元する
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(BASE, "tmp_p34")
SESSION = os.path.join(TMP, "session.json")
RESUME = os.path.join(BASE, "resume.json")

os.makedirs(TMP, exist_ok=True)
os.environ["MPLAYER_SESSION_FILE"] = SESSION
if os.path.isfile(RESUME):
    os.remove(RESUME)

from helpers import (check, finish, make_app,  # noqa: E402
                     patch_message_boxes, silence, wait_until)

from PySide6.QtCore import QEventLoop, Qt, QTimer  # noqa: E402
from PySide6.QtMultimedia import QMediaPlayer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QMenu  # noqa: E402

from main import (REPEAT_MENU_LABELS, REPEAT_MODES,  # noqa: E402
                  REPEAT_SHORT_LABELS, SHORTCUTS, HELP_NOTES, PlayerWindow)

SRC = os.path.join(BASE, "test_640x360.mp4")
NAMES = ("a", "b", "c")
PATHS = {n: os.path.join(TMP, n + ".mp4") for n in NAMES}
# プレイリストに入れない動画 (リスト外から「次へ」の確認用)
OUTSIDE = os.path.join(TMP, "outside.mp4")
PLAYING = QMediaPlayer.PlaybackState.PlayingState


def pump(ms=0):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def base(path):
    return os.path.basename(path or "")


def play_to_end(w, near=None):
    """終端近くへ移動し、シークが効いたことを確かめる。"""
    dur = w.player.duration()
    target = near if near is not None else max(0, dur - 500)
    w.player.setPosition(target)
    return wait_until(lambda: w.player.position() >= target - 400, 4000)


def press_until(w, key, mods, cond, tries=4):
    """ショートカットが効くまで押す。

    この環境ではウィンドウが前面に無いと最初の数回が落ちることがある
    (アクティブウィンドウにしかショートカットが届かないため)。押下そのもの
    ではなく「キーで操作できること」を確かめるのが目的なので、効くまで
    押し直す。効果が出た時点で True を返す。
    """
    for _ in range(tries):
        QTest.keyClick(w, key, mods)
        pump(80)
        if cond():
            return True
    return False


def main():
    patch_message_boxes()
    make_app()
    for n in NAMES:
        shutil.copyfile(SRC, PATHS[n])
    shutil.copyfile(SRC, OUTSIDE)

    # --- 定数とラベル ---
    check("リピートは 3 モード", REPEAT_MODES == ("off", "one", "all"),
          str(REPEAT_MODES))
    check("巡回順は なし → 1 本 → 全曲",
          REPEAT_MODES[0] == "off" and REPEAT_MODES[1] == "one"
          and REPEAT_MODES[2] == "all")
    check("メニュー表記が 3 つ揃う",
          all(m in REPEAT_MENU_LABELS for m in REPEAT_MODES),
          str(sorted(REPEAT_MENU_LABELS)))
    check("短縮表記が 3 つ揃う",
          all(m in REPEAT_SHORT_LABELS for m in REPEAT_MODES),
          str(sorted(REPEAT_SHORT_LABELS)))
    check("短縮表記は「全曲」", REPEAT_SHORT_LABELS["all"] == "全曲",
          REPEAT_SHORT_LABELS["all"])
    check("メニュー表記は「1 本リピート」", REPEAT_MENU_LABELS["one"] == "1 本リピート",
          REPEAT_MENU_LABELS["one"])

    # --- ドキュメント ---
    shortcuts = dict(SHORTCUTS)
    check("ショートカット表に Shift+S", "Shift+S" in shortcuts, str(list(shortcuts)))
    check("ショートカット表に Shift+R", "Shift+R" in shortcuts)
    check("Shift+S の説明がシャッフル", "シャッフル" in shortcuts.get("Shift+S", ""),
          shortcuts.get("Shift+S", ""))
    check("Shift+R の説明がリピート", "リピート" in shortcuts.get("Shift+R", ""),
          shortcuts.get("Shift+R", ""))
    check("ヘルプにシャッフルの説明", any("シャッフル" in n for n in HELP_NOTES),
          str([n for n in HELP_NOTES if "シャッフル" in n]))
    with open(os.path.join(BASE, "README.md"), encoding="utf-8") as f:
        readme = f.read()
    check("README に Shift+S", "Shift+S" in readme)
    check("README に Shift+R", "Shift+R" in readme)
    check("README にシャッフル", "シャッフル" in readme)

    # --- UI 構成 ---
    w = PlayerWindow()
    w.show()
    pump(200)  # ショートカットが届くまで少し回す (オフスクリーンでは初回が落ちる)
    silence(w)
    w._resume = {}
    check("既定はシャッフル OFF", w.shuffle_enabled() is False)
    check("既定はリピートなし", w.repeat_mode() == "off", w.repeat_mode())
    check("既定の表示", w.play_mode_text() == "シャッフル OFF / リピート: なし",
          w.play_mode_text())
    check("ボタンの初期表示", w.shuffle_btn.text() == "シャッフル",
          w.shuffle_btn.text())
    check("ボタンはチェックされていない", w.shuffle_btn.isChecked() is False)
    check("リピートボタンの初期表示", w.repeat_btn.text() == "リピート: なし",
          w.repeat_btn.text())
    check("シャッフルのキーは Shift+S",
          w.shuffle_act.shortcut().toString() == "Shift+S",
          w.shuffle_act.shortcut().toString())
    check("リピートのキーは Shift+R",
          w.repeat_act.shortcut().toString() == "Shift+R",
          w.repeat_act.shortcut().toString())
    check("シャッフルはウィンドウ全体で有効",
          w.shuffle_act in w.actions())
    check("リピートはウィンドウ全体で有効", w.repeat_act in w.actions())
    check("ボタンはフォーカスを取らない (Space と二重にならない)",
          w.shuffle_btn.focusPolicy() == Qt.FocusPolicy.NoFocus
          and w.repeat_btn.focusPolicy() == Qt.FocusPolicy.NoFocus)
    menus = {m.title(): m for m in w.menuBar().findChildren(QMenu)}
    play_menu = menus.get("再生")
    play_items = [a.text() for a in play_menu.actions()] if play_menu else []
    check("再生メニューに「シャッフル再生」", "シャッフル再生" in play_items,
          str(play_items))
    check("再生メニューに「リピート切替」", "リピート切替" in play_items,
          str(play_items))
    repeat_items = [a.text() for a in w._repeat_menu.actions()]
    check("リピートのサブメニューに 3 項目",
          repeat_items == [REPEAT_MENU_LABELS[m] for m in REPEAT_MODES],
          str(repeat_items))
    check("既定では「リピートなし」がチェック",
          w._repeat_acts["off"].isChecked() is True
          and w._repeat_acts["all"].isChecked() is False)

    # --- 切り替え (ボタン / メソッド) ---
    check("toggle で ON", w.toggle_shuffle() is None and w.shuffle_enabled() is True)
    check("ボタン表示が変わる", w.shuffle_btn.text() == "シャッフル ON",
          w.shuffle_btn.text())
    check("アクションもチェックされる", w.shuffle_act.isChecked() is True)
    check("操作系にメッセージが出る",
          w.shot_label.text() == "シャッフル ON / リピート: なし",
          w.shot_label.text())
    check("toggle で OFF に戻る", w.toggle_shuffle() is None
          and w.shuffle_enabled() is False)
    check("OFF で順番は破棄される", w._shuffle_paths == [], str(w._shuffle_paths))
    check("cycle 1 回目", w.cycle_repeat() == "one", w.repeat_mode())
    check("ボタンに 1 本と出る", w.repeat_btn.text() == "リピート: 1 本",
          w.repeat_btn.text())
    check("メニューのチェックも移る", w._repeat_acts["one"].isChecked() is True)
    check("cycle 2 回目", w.cycle_repeat() == "all", w.repeat_mode())
    check("cycle 3 回目で戻る", w.cycle_repeat() == "off", w.repeat_mode())
    check("cycle のメッセージ",
          w.shot_label.text() == "シャッフル OFF / リピート: なし",
          w.shot_label.text())
    check("不正なモードは無視", w.set_repeat("bogus") == "off", w.repeat_mode())
    check("大文字も無視", w.set_repeat("ALL") == "off", w.repeat_mode())
    w._clear_shot_message()
    check("notify=False は無言", (w.set_repeat("all", notify=False), 
          w.shot_label.text() == "")[1], w.shot_label.text())
    w.set_repeat("off", notify=False)

    # --- キー操作 ---
    w.set_shuffle(False, notify=False)
    w.set_repeat("off", notify=False)
    w.activateWindow()
    w.raise_()
    pump(150)
    check("Shift+S でシャッフル ON",
          press_until(w, Qt.Key.Key_S, Qt.KeyboardModifier.ShiftModifier,
                      lambda: w.shuffle_enabled() is True))
    check("Shift+S では字幕は変わらない", w._subs_pref is True)
    check("もう一度で OFF",
          press_until(w, Qt.Key.Key_S, Qt.KeyboardModifier.ShiftModifier,
                      lambda: w.shuffle_enabled() is False))
    check("Shift+R でリピートが進む (off → one)",
          press_until(w, Qt.Key.Key_R, Qt.KeyboardModifier.ShiftModifier,
                      lambda: w.repeat_mode() == "one"), w.repeat_mode())
    check("続けて all になる",
          press_until(w, Qt.Key.Key_R, Qt.KeyboardModifier.ShiftModifier,
                      lambda: w.repeat_mode() == "all"), w.repeat_mode())
    check("3 回目で一周して off に戻る",
          press_until(w, Qt.Key.Key_R, Qt.KeyboardModifier.ShiftModifier,
                      lambda: w.repeat_mode() == "off"), w.repeat_mode())

    # --- シャッフル順 (プレイリストあり) ---
    w.set_shuffle(False, notify=False)
    check("3 件を追加", w.add_to_playlist([PATHS[n] for n in NAMES]) == 3)
    check("表示順は追加順", [base(p) for p in w.playlist_paths()] ==
          ["a.mp4", "b.mp4", "c.mp4"], str([base(p) for p in w.playlist_paths()]))
    check("b を再生", w.play_index(1) is True, base(w._current_path))
    w.set_shuffle(True, notify=False)
    check("順番は 3 件の置換", sorted(w._shuffle_paths) == sorted(w.playlist_paths())
          and len(w._shuffle_paths) == 3, str([base(p) for p in w._shuffle_paths]))
    check("再生中の曲が先頭に残る", w._shuffle_paths[0] == os.path.abspath(PATHS["b"]),
          base(w._shuffle_paths[0]))

    # 順番を固定して送り / 戻しを確かめる
    w._shuffle_paths = [PATHS[n] for n in ("b", "c", "a")]
    w.play_index(1)
    check("次へはシャッフル順 (b → c)", w.play_next() is True
          and w._current_path == os.path.abspath(PATHS["c"]), base(w._current_path))
    check("さらに次へ (c → a)", w.play_next() is True
          and w._current_path == os.path.abspath(PATHS["a"]), base(w._current_path))
    check("端でリピートなしなら進まない", w.play_next() is False,
          base(w._current_path))
    check("端では曲も変わらない", w._current_path == os.path.abspath(PATHS["a"]),
          base(w._current_path))
    check("逆向きにも辿れる (a → c)", w.play_prev() is True
          and w._current_path == os.path.abspath(PATHS["c"]), base(w._current_path))
    check("さらに戻る (c → b)", w.play_prev() is True
          and w._current_path == os.path.abspath(PATHS["b"]), base(w._current_path))
    check("先頭で戻っても進まない (リピートなし)", w.play_prev() is False,
          base(w._current_path))

    # リスト外のファイルから進むときは順番の先頭に入る
    w._shuffle_paths = [PATHS[n] for n in ("c", "a", "b")]
    check("リスト外の動画を開く", w.load(OUTSIDE), base(w._current_path))
    check("リスト外から次へで順番の先頭へ", w.play_next() is True
          and w._current_path == os.path.abspath(PATHS["c"]), base(w._current_path))
    w.load(OUTSIDE)
    check("リスト外から前へで順番の末尾へ", w.play_prev() is True
          and w._current_path == os.path.abspath(PATHS["b"]), base(w._current_path))

    # --- 端での折り返し (全曲リピート) ---
    w.set_repeat("all", notify=False)
    w._shuffle_paths = [PATHS[n] for n in ("b", "c", "a")]
    w.play_index(1)
    w.play_next()
    check("全曲リピートでは端から折り返す", w.play_next() is True,
          base(w._current_path))
    check("折り返し先はリスト内", w._current_path in w.playlist_paths(),
          base(w._current_path))
    check("折り返し後も順番は 3 件の置換",
          sorted(w._shuffle_paths) == sorted(w.playlist_paths())
          and len(w._shuffle_paths) == 3,
          str([base(p) for p in w._shuffle_paths]))
    check("表示順でも端から折り返す", (w.set_shuffle(False, notify=False),
          w.play_index(2), w.play_next() is True
          and w._current_path == os.path.abspath(PATHS["a"]))[2],
          base(w._current_path))

    # --- シャッフル OFF は表示順 ---
    w.set_repeat("off", notify=False)
    w.set_shuffle(False, notify=False)
    check("OFF で順番は空", w._shuffle_paths == [], str(w._shuffle_paths))
    w.play_index(0)
    check("表示順に進む (a → b)", w.play_next() is True
          and w._current_path == os.path.abspath(PATHS["b"]), base(w._current_path))
    check("戻れる (b → a)", w.play_prev() is True
          and w._current_path == os.path.abspath(PATHS["a"]), base(w._current_path))
    check("先頭で戻っても進まない", w.play_prev() is False, base(w._current_path))

    # --- プレイリストの変更に追従する ---
    w.set_shuffle(True, notify=False)
    w._shuffle_paths = [PATHS[n] for n in ("b", "c", "a")]
    w.playlist.takeItem(2)  # c を削除
    check("消えたパスは順番からも消える",
          [base(p) for p in w._shuffle_order()] == ["b.mp4", "a.mp4"],
          str([base(p) for p in w._shuffle_order()]))
    check("追加したパスは末尾に入る",
          (w.add_to_playlist([PATHS["c"]]),
           sorted(w._shuffle_order()) == sorted(w.playlist_paths()),
           len(w._shuffle_order()) == 3)[2],
          str([base(p) for p in w._shuffle_order()]))
    w.clear_playlist()
    check("クリアで順番も空", w._shuffle_order() == [], str(w._shuffle_paths))
    check("空なら次へは進まない", w.play_next() is False)
    check("空なら前へも進まない", w.play_prev() is False)
    check("空のままシャッフル ON にしても落ちない",
          (w.set_shuffle(True, notify=False) is True))
    check("後から追加した曲は次に進むときに並ぶ",
          (w.add_to_playlist([PATHS["a"]]),
           w._shuffle_order() == [os.path.abspath(PATHS["a"])])[1],
          str([base(p) for p in w._shuffle_order()]))
    check("空でも切り替えは落ちない",
          (w.set_shuffle(False, notify=False), w.set_repeat("one", notify=False),
           w.shuffle_enabled() is False and w.repeat_mode() == "one")[2])

    # --- リピート (終端 = EOS の実挙動) ---
    w.add_to_playlist([PATHS[n] for n in NAMES])
    w.set_repeat("one", notify=False)
    w.set_shuffle(False, notify=False)
    check("a を再生", w.play_index(0) is True, base(w._current_path))
    check("終端近くへ", play_to_end(w), str(w.player.position()))
    check("1 本リピートは同じ曲を先頭から", wait_until(
        lambda: w.player.position() < 1200, 9000), str(w.player.position()))
    check("1 本リピート中は曲が変わらない",
          w._current_path == os.path.abspath(PATHS["a"]), base(w._current_path))
    check("1 本リピート中は再生が続く",
          w.player.playbackState() == PLAYING, str(w.player.playbackState()))
    check("1 本リピートはリストが空でも効く", (
        w.clear_playlist(), w._advance_if_in_playlist())[1] is True,
        base(w._current_path))
    check("リストが空でも曲は同じ",
          w._current_path == os.path.abspath(PATHS["a"]), base(w._current_path))

    # リピートなし: 最後の曲で終わったら停止表示
    w.add_to_playlist([PATHS[n] for n in NAMES])
    w.set_repeat("off", notify=False)
    check("最後の曲を再生", w.play_index(2) is True, base(w._current_path))
    check("終端近くへ", play_to_end(w), str(w.player.position()))
    check("リピートなしなら停止する", wait_until(
        lambda: w.player.playbackState() != PLAYING, 9000),
        str(w.player.playbackState()))
    check("停止して先頭に戻る", w.player.position() < 800, str(w.player.position()))
    check("曲は変わらない", w._current_path == os.path.abspath(PATHS["c"]),
          base(w._current_path))
    check("終了の表示が出る", "(終了)" in w.time_label.text(), w.time_label.text())

    # 全曲リピート: 最後の曲で終わったら先頭の曲へ
    w.set_repeat("all", notify=False)
    w.play_index(2)
    check("終端近くへ", play_to_end(w), str(w.player.position()))
    check("全曲リピートは次の曲 (先頭) へ", wait_until(
        lambda: w._current_path == os.path.abspath(PATHS["a"]), 9000),
        base(w._current_path))
    check("続けて再生される", wait_until(
        lambda: w.player.playbackState() == PLAYING, 5000),
        str(w.player.playbackState()))

    # 全曲リピートで 1 曲だけなら同じ曲を繰り返す
    w.clear_playlist()
    w.add_to_playlist([PATHS["b"]])
    w.play_index(0)
    check("1 曲だけでも終端へ", play_to_end(w), str(w.player.position()))
    check("1 曲の全曲リピートは先頭から", wait_until(
        lambda: w.player.position() < 1200, 9000), str(w.player.position()))
    check("1 曲の全曲リピートでも曲は同じ",
          w._current_path == os.path.abspath(PATHS["b"]), base(w._current_path))
    w.set_repeat("off", notify=False)

    # --- 保存と復元 ---
    w.clear_playlist()
    w.add_to_playlist([PATHS[n] for n in NAMES])
    w.set_shuffle(True, notify=False)
    w.set_repeat("all", notify=False)
    w._save_session()
    with open(SESSION, encoding="utf-8") as f:
        data = json.load(f)
    check("シャッフルが保存される", data.get("shuffle") is True,
          str(data.get("shuffle")))
    check("リピートが保存される", data.get("repeat") == "all",
          str(data.get("repeat")))

    w2 = PlayerWindow()
    silence(w2)
    w2._resume = {}
    check("復元前の既定は OFF", w2.shuffle_enabled() is False)
    w2._apply_session(data)
    check("シャッフルが復元される", w2.shuffle_enabled() is True)
    check("リピートが復元される", w2.repeat_mode() == "all", w2.repeat_mode())
    check("復元後はメッセージを出さない", w2.shot_label.text() == "",
          w2.shot_label.text())
    check("復元後の表示も一致", w2.shuffle_btn.text() == "シャッフル ON"
          and w2.repeat_btn.text() == "リピート: 全曲",
          f"{w2.shuffle_btn.text()} / {w2.repeat_btn.text()}")
    check("復元後のメニューも一致",
          w2._repeat_acts["all"].isChecked() is True
          and w2.shuffle_act.isChecked() is True)
    check("復元したプレイリストで順番が作られる",
          sorted(w2._shuffle_paths) == sorted(w2.playlist_paths())
          and len(w2._shuffle_paths) == 3,
          str([base(p) for p in w2._shuffle_paths]))

    w3 = PlayerWindow()
    silence(w3)
    w3._resume = {}
    w3._apply_session({"shuffle": "yes"})
    check("文字列のシャッフルは無視", w3.shuffle_enabled() is False)
    w3._apply_session({"shuffle": 1})
    check("数値のシャッフルも無視", w3.shuffle_enabled() is False)
    w3._apply_session({"repeat": "ALL"})
    check("大文字のリピートは無視", w3.repeat_mode() == "off", w3.repeat_mode())
    w3._apply_session({"repeat": 1})
    check("数値のリピートも無視", w3.repeat_mode() == "off", w3.repeat_mode())
    w3._apply_session({"repeat": "one"})
    check("正しいリピートは反映", w3.repeat_mode() == "one", w3.repeat_mode())
    w3._apply_session({"shuffle": True, "repeat": "off"})
    check("正しいシャッフルも反映", w3.shuffle_enabled() is True)
    check("リピートも一緒に反映", w3.repeat_mode() == "off", w3.repeat_mode())

    # --- 後始末 ---
    for win in (w, w2, w3):
        try:
            win.close()
        except Exception:
            pass
    if os.path.isfile(RESUME):
        os.remove(RESUME)
    shutil.rmtree(TMP, ignore_errors=True)
    return finish("P34shufflerepeat")


if __name__ == "__main__":
    sys.exit(main())
