"""P32: 字幕の遅延 (同期ズレ) 調整。

- Shift+, / Shift+. で 0.1 秒ずつ早める / 遅らせる
- 「字幕」→「遅延」からも操作できる
- ±10 秒で止まり、値は session.json に保存して次回復元する
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(BASE, "tmp_p32")
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

from main import (SUB_DELAY_LIMIT_MS, SUB_DELAY_STEP_MS,  # noqa: E402
                  HELP_NOTES, SHORTCUTS, PlayerWindow, clamp_sub_delay,
                  format_sub_delay)

SRC = os.path.join(BASE, "test_640x360.mp4")
CLIP = os.path.join(TMP, "clip.mp4")
CLIP2 = os.path.join(TMP, "clip2.mp4")
CLIP_SRT = os.path.join(TMP, "clip.srt")

# 1-2 秒と 3-4 秒に字幕 (間は 1 秒空ける)。遅延の向きを判定しやすくする。
SRT_TEXT = (
    "1\n"
    "00:00:01,000 --> 00:00:02,000\n"
    "いち\n"
    "\n"
    "2\n"
    "00:00:03,000 --> 00:00:04,000\n"
    "さん\n"
)

SHIFT_PERIOD = (Qt.Key.Key_Period, Qt.KeyboardModifier.ShiftModifier)
SHIFT_COMMA = (Qt.Key.Key_Comma, Qt.KeyboardModifier.ShiftModifier)


def pump(ms=0):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def flash(w, key, mods):
    QTest.keyClick(w, key, mods)
    pump(30)


def main():
    patch_message_boxes()
    make_app()

    shutil.copyfile(SRC, CLIP)
    shutil.copyfile(SRC, CLIP2)
    with open(CLIP_SRT, "w", encoding="utf-8") as f:
        f.write(SRT_TEXT)

    # --- 定数と純粋関数 ---
    check("1 回の調整は 0.1 秒", SUB_DELAY_STEP_MS == 100, str(SUB_DELAY_STEP_MS))
    check("上限は 10 秒", SUB_DELAY_LIMIT_MS == 10000, str(SUB_DELAY_LIMIT_MS))
    check("0 の表示", format_sub_delay(0) == "0 秒", format_sub_delay(0))
    check("+0.1 秒の表示", format_sub_delay(100) == "+0.1 秒",
          format_sub_delay(100))
    check("-0.1 秒の表示", format_sub_delay(-100) == "-0.1 秒",
          format_sub_delay(-100))
    check("+1.0 秒の表示", format_sub_delay(1000) == "+1.0 秒",
          format_sub_delay(1000))
    check("-2.5 秒の表示", format_sub_delay(-2500) == "-2.5 秒",
          format_sub_delay(-2500))
    check("丸め: 0 はそのまま", clamp_sub_delay(0) == 0)
    check("丸め: 範囲内はそのまま", clamp_sub_delay(500) == 500)
    check("丸め: 上限を超えたら上限", clamp_sub_delay(20000) == 10000,
          str(clamp_sub_delay(20000)))
    check("丸め: 下限を超えたら下限", clamp_sub_delay(-20000) == -10000,
          str(clamp_sub_delay(-20000)))

    # --- ドキュメント ---
    shortcuts = dict(SHORTCUTS)
    check("ショートカット表に Shift+, / Shift+.",
          "Shift+, / Shift+." in shortcuts, str(list(shortcuts)))
    check("ショートカット表の説明が字幕", "字幕" in shortcuts.get(
        "Shift+, / Shift+.", ""), str(shortcuts.get("Shift+, / Shift+.")))
    check("ヘルプに遅延の説明", any("遅延" in n for n in HELP_NOTES),
          str([n for n in HELP_NOTES if "遅延" in n]))
    with open(os.path.join(BASE, "README.md"), encoding="utf-8") as f:
        readme = f.read()
    check("README にショートカット", "Shift+, / Shift+." in readme)
    check("README に字幕の遅延", "字幕の遅延" in readme)

    # --- メニューとキー ---
    w = PlayerWindow()
    w.show()
    silence(w)
    w._resume = {}

    menus = {m.title(): m for m in w.menuBar().findChildren(QMenu)}
    sub_menu = menus.get("字幕")
    sub_menus = {m.title(): m for m in sub_menu.findChildren(QMenu)} if sub_menu else {}
    delay_labels = [m.title() for m in sub_menus]
    check("字幕メニューに遅延サブメニューがある",
          any(t.startswith("遅延") for t in delay_labels), str(delay_labels))
    delay_menu = next((m for t, m in sub_menus.items() if t.startswith("遅延")),
                      None)
    delay_items = [a.text() for a in delay_menu.actions()] if delay_menu else []
    check("遅延メニューに「遅らせる」がある",
          "字幕を 0.1 秒遅らせる" in delay_items, str(delay_items))
    check("遅延メニューに「早める」がある",
          "字幕を 0.1 秒早める" in delay_items, str(delay_items))
    check("遅延メニューにリセットがある", "遅延をリセット" in delay_items,
          str(delay_items))
    check("遅延メニューに現在値の表示がある",
          any(a.startswith("現在: ") for a in delay_items), str(delay_items))
    check("現在値の表示は押せない", w.sub_delay_info_act.isEnabled() is False)
    check("遅らせる = Shift+.", w.sub_delay_act.shortcut().toString() == "Shift+.",
          w.sub_delay_act.shortcut().toString())
    check("早める = Shift+,", w.sub_advance_act.shortcut().toString() == "Shift+,",
          w.sub_advance_act.shortcut().toString())
    check("遅らせるはウィンドウ全体で有効",
          w.sub_delay_act.shortcutContext() == Qt.ShortcutContext.WindowShortcut,
          str(w.sub_delay_act.shortcutContext()))
    check("早めるもウィンドウ全体で有効",
          w.sub_advance_act.shortcutContext() == Qt.ShortcutContext.WindowShortcut,
          str(w.sub_advance_act.shortcutContext()))
    check("遅らせるはウィンドウにも登録", w.sub_delay_act in w.actions())
    check("早めるもウィンドウに登録", w.sub_advance_act in w.actions())
    check("フレーム送りのキーとは別", w.step_fwd_act.shortcut().toString() == ".",
          w.step_fwd_act.shortcut().toString())

    # --- 既定値と未ロード時の操作 ---
    check("既定の遅延は 0", w.sub_delay_ms() == 0, str(w.sub_delay_ms()))
    check("現在値の表示は 0 秒", w.sub_delay_info_act.text() == "現在: 0 秒",
          w.sub_delay_info_act.text())
    check("未ロードでも遅らせられる", w.delay_subtitles() is None)
    check("未ロードでも 0.1 秒になる", w.sub_delay_ms() == 100,
          str(w.sub_delay_ms()))
    check("表示も更新される", w.sub_delay_info_act.text() == "現在: +0.1 秒",
          w.sub_delay_info_act.text())
    check("未ロードでも早められる", w.advance_subtitles() is None)
    check("戻って 0 秒", w.sub_delay_ms() == 0, str(w.sub_delay_ms()))
    w.update_subtitle(1500)
    check("字幕が無ければ何も出ない", w.subtitle_label.text() == "",
          w.subtitle_label.text())
    check("操作系にメッセージが出る", w.shot_label.text() == "字幕の遅延: 0 秒",
          w.shot_label.text())
    check("メッセージは表示される", w.shot_label.isVisible())
    check("nudge は加算", w.nudge_sub_delay(300) == 300, str(w.sub_delay_ms()))
    check("nudge で表示も更新", w.sub_delay_info_act.text() == "現在: +0.3 秒",
          w.sub_delay_info_act.text())
    check("リセットで 0 に戻る", w.reset_sub_delay() is None and w.sub_delay_ms() == 0,
          str(w.sub_delay_ms()))

    # --- ロードして字幕を読む ---
    check("動画を開く", w.load(CLIP))
    check("cues を読んだ", wait_until(lambda: len(w._cues) == 2, 5000),
          str(w._cues))
    w.player.pause()
    check("一時停止した", wait_until(
        lambda: w.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState,
        3000))
    check("字幕は表示状態", w._subs_enabled is True)
    w.update_subtitle(1500)
    check("1.5 秒で 1 つ目の字幕", w.subtitle_label.text() == "いち",
          w.subtitle_label.text())
    w.update_subtitle(2500)
    check("隙間では出ない", w.subtitle_label.text() == "",
          w.subtitle_label.text())
    w.update_subtitle(3500)
    check("3.5 秒で 2 つ目の字幕", w.subtitle_label.text() == "さん",
          w.subtitle_label.text())

    # --- 遅らせる (+): 字幕が遅れて出る ---
    check("+1.0 秒にする", w.set_sub_delay(1000) == 1000, str(w.sub_delay_ms()))
    w.update_subtitle(1500)
    check("遅らせると 1.5 秒では出ない", w.subtitle_label.text() == "",
          w.subtitle_label.text())
    w.update_subtitle(2500)
    check("ずらした位置で 1 つ目が出る", w.subtitle_label.text() == "いち",
          w.subtitle_label.text())
    w.update_subtitle(3500)
    check("元の 3.5 秒では出ない (2 つ目)", w.subtitle_label.text() == "",
          w.subtitle_label.text())
    w.update_subtitle(4500)
    check("ずらした位置で 2 つ目が出る", w.subtitle_label.text() == "さん",
          w.subtitle_label.text())

    # --- 早める (-): 字幕が早く出る ---
    w.reset_sub_delay()
    check("リセットで元に戻る", w.sub_delay_ms() == 0, str(w.sub_delay_ms()))
    check("-1.0 秒にする", w.set_sub_delay(-1000) == -1000, str(w.sub_delay_ms()))
    w.update_subtitle(500)
    check("早めると 0.5 秒で出る", w.subtitle_label.text() == "いち",
          w.subtitle_label.text())
    w.update_subtitle(1500)
    check("元の 1.5 秒では出ない", w.subtitle_label.text() == "",
          w.subtitle_label.text())
    w.update_subtitle(2500)
    check("早めた 2 つ目は 2.5 秒で出る", w.subtitle_label.text() == "さん",
          w.subtitle_label.text())
    w.reset_sub_delay()
    w.update_subtitle(1500)
    check("リセット後は元の位置で出る", w.subtitle_label.text() == "いち",
          w.subtitle_label.text())

    # --- 上限で止まる ---
    check("上限を超えない", w.set_sub_delay(20000) == SUB_DELAY_LIMIT_MS,
          str(w.sub_delay_ms()))
    check("上限の表示", w.sub_delay_info_act.text() == "現在: +10.0 秒",
          w.sub_delay_info_act.text())
    check("上限では増えない", w.nudge_sub_delay(SUB_DELAY_STEP_MS) ==
          SUB_DELAY_LIMIT_MS, str(w.sub_delay_ms()))
    check("上限でもメッセージは出る",
          w.shot_label.text() == "字幕の遅延: +10.0 秒", w.shot_label.text())
    check("下限を超えない", w.set_sub_delay(-20000) == -SUB_DELAY_LIMIT_MS,
          str(w.sub_delay_ms()))
    check("下限では減らない", w.nudge_sub_delay(-SUB_DELAY_STEP_MS) ==
          -SUB_DELAY_LIMIT_MS, str(w.sub_delay_ms()))
    w.reset_sub_delay()

    # --- キー操作 (Shift+.) ---
    # 位置は境界から十分離した場所で、即時反映も確かめる
    # (遅延 1.0 秒で消える位置 = 1.0〜2.0 秒のどこか)
    w.player.setPosition(1500)
    check("1.5 秒へ移動", wait_until(
        lambda: abs(w.player.position() - 1500) < 300, 3000),
        str(w.player.position()))
    w.update_subtitle(w.player.position())
    check("移動先で字幕が出る", w.subtitle_label.text() == "いち",
          w.subtitle_label.text())
    w.set_sub_delay(1000)
    check("遅延で表示中の字幕が即座に消える", w.subtitle_label.text() == "",
          w.subtitle_label.text())
    w.reset_sub_delay()
    check("リセットで表示が戻る", w.subtitle_label.text() == "いち",
          w.subtitle_label.text())
    flash(w, *SHIFT_PERIOD)
    check("Shift+. で 0.1 秒遅れる", w.sub_delay_ms() == 100,
          str(w.sub_delay_ms()))
    flash(w, *SHIFT_PERIOD)
    flash(w, *SHIFT_PERIOD)
    check("連続入力で加算される", w.sub_delay_ms() == 300, str(w.sub_delay_ms()))
    check("キーでもメッセージが出る",
          w.shot_label.text() == "字幕の遅延: +0.3 秒", w.shot_label.text())
    flash(w, *SHIFT_COMMA)
    check("Shift+, で 0.1 秒戻る", w.sub_delay_ms() == 200, str(w.sub_delay_ms()))
    w.reset_sub_delay()

    # 再生中に押しても止まらない (コマ送りとは違う)
    w.player.setPosition(1000)
    w.player.play()
    check("再生を開始", wait_until(
        lambda: w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState,
        3000))
    flash(w, *SHIFT_PERIOD)
    check("Shift+. は再生を止めない", w.player.playbackState() ==
          QMediaPlayer.PlaybackState.PlayingState)
    check("再生中でも遅延は変わる", w.sub_delay_ms() == 100, str(w.sub_delay_ms()))
    w.player.pause()
    pump(200)
    w.reset_sub_delay()

    # --- 字幕 OFF のときは出ない (値は保持) ---
    check("遅延を 0.5 秒にする", w.set_sub_delay(500) == 500, str(w.sub_delay_ms()))
    w.set_subtitles_pref(False)
    check("OFF では表示しない", w._subs_enabled is False)
    w.update_subtitle(1500)
    check("OFF ではラベルも空", w.subtitle_label.text() == "",
          w.subtitle_label.text())
    check("OFF でも値は保持", w.sub_delay_ms() == 500, str(w.sub_delay_ms()))
    w.set_subtitles_pref(True)
    w.update_subtitle(1300)
    check("ON に戻すと遅延が効く", w.subtitle_label.text() == "",
          w.subtitle_label.text())
    w.update_subtitle(1600)
    check("ON に戻すとずらした位置で出る", w.subtitle_label.text() == "いち",
          w.subtitle_label.text())

    # --- 保存と復元 ---
    w._save_session()
    with open(SESSION, encoding="utf-8") as f:
        data = json.load(f)
    check("遅延が保存される", data.get("subtitle_delay_ms") == 500,
          str(data.get("subtitle_delay_ms")))

    w2 = PlayerWindow()
    silence(w2)
    w2._resume = {}
    check("復元前の既定は 0", w2.sub_delay_ms() == 0, str(w2.sub_delay_ms()))
    w2._apply_session(data)
    check("遅延が復元される", w2.sub_delay_ms() == 500, str(w2.sub_delay_ms()))
    check("復元後はメッセージを出さない", w2.shot_label.text() == "",
          w2.shot_label.text())
    check("復元後の表示も一致", w2.sub_delay_info_act.text() == "現在: +0.5 秒",
          w2.sub_delay_info_act.text())

    w3 = PlayerWindow()
    silence(w3)
    w3._resume = {}
    w3._apply_session({"subtitle_delay_ms": "0.5"})
    check("文字列は無視される", w3.sub_delay_ms() == 0, str(w3.sub_delay_ms()))
    w3._apply_session({"subtitle_delay_ms": True})
    check("真偽値は無視される", w3.sub_delay_ms() == 0, str(w3.sub_delay_ms()))
    w3._apply_session({"subtitle_delay_ms": -99999})
    check("保存値も上限内に丸める", w3.sub_delay_ms() == -SUB_DELAY_LIMIT_MS,
          str(w3.sub_delay_ms()))
    w3._apply_session({"subtitle_delay_ms": 700})
    check("正しい値は反映される", w3.sub_delay_ms() == 700, str(w3.sub_delay_ms()))

    # --- 別の動画を開いても値は残る (全動画共通の設定) ---
    w3.load(CLIP2)
    check("別の動画を開いても残る", w3.sub_delay_ms() == 700,
          str(w3.sub_delay_ms()))

    # --- 他の操作を壊さない ---
    w.reset_sub_delay()
    w.update_subtitle(1500)
    check("A-B とは独立に字幕が出る", w.subtitle_label.text() == "いち",
          w.subtitle_label.text())
    pos_before = w.player.position()
    w.set_sub_delay(300)
    check("遅延を変えても位置は動かない",
          abs(w.player.position() - pos_before) < 200,
          f"{pos_before} -> {w.player.position()}")
    check("字幕の表示状態は変わらない", w._subs_enabled is True)

    # --- 後始末 ---
    for win in (w, w2, w3):
        try:
            win.close()
        except Exception:
            pass
    if os.path.isfile(RESUME):
        os.remove(RESUME)
    shutil.rmtree(TMP, ignore_errors=True)
    return finish("P32subdelay")


if __name__ == "__main__":
    sys.exit(main())
