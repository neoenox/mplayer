"""P30: 1 フレーム送り (, / .) とプロパティ (メディア情報)。

- fps から 1 フレーム長を求め、端では動かないこと
- 再生中に押したら一時停止してから移動すること
- 取得できないメタデータ (コーデック enum 等) でプロパティが落ちないこと
- 未ロードでもプロパティが落ちないこと
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(BASE, "tmp_p30")
SESSION = os.path.join(TMP, "session.json")
RESUME = os.path.join(BASE, "resume.json")
CLIP = os.path.join(TMP, "clip.mp4")

shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(TMP, exist_ok=True)
os.environ["MPLAYER_SESSION_FILE"] = SESSION
if os.path.isfile(RESUME):
    os.remove(RESUME)

from helpers import (check, dialog_calls, finish, make_app,  # noqa: E402
                     patch_message_boxes, silence, wait_for_frame, wait_until)

from PySide6.QtCore import QEventLoop, Qt, QTimer  # noqa: E402
from PySide6.QtMultimedia import QMediaMetaData, QMediaPlayer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QMenu  # noqa: E402

from main import (FRAME_STEP_FALLBACK_MS, HELP_NOTES,  # noqa: E402
                  META_ROWS, SHORTCUTS, PlayerWindow, _fmt_codec,
                  frame_step_ms_for)

SRC = os.path.join(BASE, "test_640x360.mp4")
LONG = os.path.join(BASE, "test_60s.mp4")  # レジューム対象になる長さの動画


def pump(ms=0):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def pos_now(w):
    """適用済みの再生位置 (遅延シークを待たずに読める値)。"""
    pending = w._pending_seek
    return pending if pending is not None else w.player.position()


def main():
    patch_message_boxes()
    make_app()
    shutil.copyfile(SRC, CLIP)

    w = PlayerWindow()
    w.show()
    silence(w)
    w._resume = {}

    # --- 構造 (アクション / メニュー) ---
    check("「1 フレーム戻る」のキーは ,",
          w.step_back_act.shortcut().toString() == ",", w.step_back_act.shortcut().toString())
    check("「1 フレーム進む」のキーは .",
          w.step_fwd_act.shortcut().toString() == ".", w.step_fwd_act.shortcut().toString())
    check("フレーム送りはウィンドウ全体で有効",
          w.step_fwd_act.shortcutContext() == Qt.ShortcutContext.WindowShortcut,
          str(w.step_fwd_act.shortcutContext()))
    menus = {m.title(): m for m in w.menuBar().findChildren(QMenu)}
    play_labels = [a.text() for a in menus["再生"].actions()] if "再生" in menus else []
    check("「再生」メニューにフレーム戻るがある",
          "1 フレーム戻る" in play_labels, str(play_labels))
    check("「再生」メニューにフレーム進むがある",
          "1 フレーム進む" in play_labels, str(play_labels))
    file_labels = [a.text() for a in menus["ファイル"].actions()] if "ファイル" in menus else []
    check("「ファイル」メニューにプロパティがある",
          "プロパティ..." in file_labels, str(file_labels))

    # --- fps -> 1 フレーム長 (純粋関数) ---
    check("30fps は 33ms", frame_step_ms_for(30) == 33, str(frame_step_ms_for(30)))
    check("25fps は 40ms", frame_step_ms_for(25) == 40, str(frame_step_ms_for(25)))
    check("60fps は 17ms", frame_step_ms_for(60) == 17, str(frame_step_ms_for(60)))
    check("24fps は 42ms", frame_step_ms_for(24) == 42, str(frame_step_ms_for(24)))
    check("fps 不明 (None) は既定値", frame_step_ms_for(None) == FRAME_STEP_FALLBACK_MS)
    check("fps 0 は既定値", frame_step_ms_for(0) == FRAME_STEP_FALLBACK_MS)
    check("fps 異常値 (数値でない) は既定値",
          frame_step_ms_for("x") == FRAME_STEP_FALLBACK_MS)
    check("fps 異常値 (大きすぎ) は既定値",
          frame_step_ms_for(1000) == FRAME_STEP_FALLBACK_MS)

    # --- 未ロード ---
    check("未ロードのフレーム長は既定値",
          w.frame_step_ms() == FRAME_STEP_FALLBACK_MS, str(w.frame_step_ms()))
    check("未ロードでは移動しない", w.step_frame(1) is False)
    check("未ロードのプロパティ情報は空", w.media_info_lines() == [],
          str(w.media_info_lines()))
    QTest.keyClick(w, Qt.Key.Key_Period)
    QTest.keyClick(w, Qt.Key.Key_Comma)
    pump(60)
    check("未ロードでキーを押しても落ちない", True)
    dialog_calls.clear()
    w.show_media_info()
    check("未ロードのプロパティは案内を出す",
          any("動画を開いていません" in str(c) for c in dialog_calls),
          str(dialog_calls))

    # --- ロード ---
    check("動画をロード", w.load(CLIP))
    check("長さを取得", wait_until(lambda: w.player.duration() > 0, 5000),
          str(w.player.duration()))
    check("fps を取得できる (30fps -> 33ms)", w.frame_step_ms() == 33,
          str(w.frame_step_ms()))
    check("映像が出る", wait_for_frame(w))
    w.player.pause()
    check("一時停止する", wait_until(
        lambda: w.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState, 3000))

    # --- プロパティ ---
    info = w.media_info_text()
    check("プロパティにファイル名が出る", "clip.mp4" in info, info)
    check("プロパティに解像度が出る", "640 x 360" in info, info)
    check("プロパティにフレームレートが出る", "30 fps" in info, info)
    check("プロパティに長さが出る", "00:05" in info, info)
    check("プロパティにサイズが出る", "MB" in info, info)
    rows = dict(w.media_info_lines())
    check("プロパティに実バイト数が入る",
          f"{os.path.getsize(CLIP):,} バイト" in rows.get("サイズ", ""),
          rows.get("サイズ", ""))
    check("使えないメタデータ項目は表示しない",
          all(not v.startswith("<") for v in rows.values()), str(rows))
    check("項目は META_ROWS の範囲内", len(rows) <= len(META_ROWS) + 4, str(len(rows)))
    # 取得できないキー (環境によりコーデック enum が変換できない) でも
    # 例外を出さず文字列を返すこと
    codec = w._meta_text(QMediaMetaData.Key.VideoCodec, _fmt_codec)
    check("取得できないキーでも文字列を返す", isinstance(codec, str), repr(codec))
    md = w.player.metaData()
    check("取得済みメタデータを渡しても同じ",
          w._meta_text(QMediaMetaData.Key.Resolution,
                       lambda s: f"{s.width()}x{s.height()}", md) == "640x360")
    check("フォーマッタが例外でも空文字",
          w._meta_text(QMediaMetaData.Key.Resolution, lambda v: 1 / 0) == "")

    class _BoomMeta:
        def value(self, key):
            raise RuntimeError("boom")

    check("メタデータ取得が例外でも空文字",
          w._meta_text(QMediaMetaData.Key.Resolution, lambda v: v, _BoomMeta()) == "")
    dialog_calls.clear()
    w.show_media_info()
    check("プロパティが表示される", len(dialog_calls) == 1, str(dialog_calls))
    check("プロパティの題は プロパティ",
          dialog_calls and dialog_calls[0][1] == "プロパティ", str(dialog_calls[:1]))
    check("プロパティ本文に解像度が入る",
          "640 x 360" in str(dialog_calls[0][2]), str(dialog_calls[:1])[:200])

    # --- 1 フレーム送り ---
    w.player.setPosition(1200)
    pump(600)
    check("起点を作れる", abs(w.player.position() - 1200) <= 50,
          str(w.player.position()))

    img_before = w.screenshot_image()
    check("進むと 33ms 進む", w.step_frame(1) is True)
    check("位置が 33ms 進む", wait_until(lambda: pos_now(w) == 1233, 3000),
          str(pos_now(w)))
    check("戻ると 33ms 戻る", w.step_frame(-1) is True)
    check("位置が 33ms 戻る", wait_until(lambda: pos_now(w) == 1200, 3000),
          str(pos_now(w)))

    # 絵の変化は 1 フレームだと同一フレームに写像され得るため 3 フレームで見る
    for _ in range(3):
        w.step_frame(1)
    check("3 フレーム進むと絵も変わる",
          wait_until(lambda: w.screenshot_image() != img_before, 3000))
    for _ in range(3):
        w.step_frame(-1)
    check("3 フレーム戻すと元の位置に戻る",
          wait_until(lambda: pos_now(w) == 1200, 3000), str(pos_now(w)))

    # 連続入力は累積する
    for _ in range(3):
        w.step_frame(1)
    check("連続入力で累積する (1200 -> 1299)",
          wait_until(lambda: pos_now(w) == 1299, 3000), str(pos_now(w)))

    # 先頭では動かない
    w.player.setPosition(0)
    pump(500)
    check("先頭では戻らない", w.step_frame(-1) is False, str(pos_now(w)))
    check("先頭の位置は 0 のまま", pos_now(w) == 0, str(pos_now(w)))

    # 終端: duration-1 で止まり、逆走も EOS も起こさない
    # (setPosition(duration) 自体が EOS を誘発し得るため手前から進める)
    end = w.player.duration()
    w.player.setPosition(end - 80)
    pump(600)
    check("終端手前から 1 フレーム進める", w.step_frame(1) is True)
    check("終端手前で 33ms 進む",
          wait_until(lambda: pos_now(w) == end - 47, 3000), str(pos_now(w)))
    check("終端に近づいても進める", w.step_frame(1) is True)
    check("2 回目は end-14", wait_until(lambda: pos_now(w) == end - 14, 3000),
          str(pos_now(w)))
    check("終端をはみ出さない", w.step_frame(1) is True)
    check("上限は duration-1", wait_until(lambda: pos_now(w) == end - 1, 3000),
          str(pos_now(w)))
    check("終端では進めない (逆走しない)", w.step_frame(1) is False,
          str(pos_now(w)))
    check("終端でも位置は duration-1 のまま", pos_now(w) == end - 1,
          str(pos_now(w)))
    check("終端からは戻れる", w.step_frame(-1) is True)
    check("終端から 33ms 戻る",
          wait_until(lambda: pos_now(w) == end - 34, 3000), str(pos_now(w)))
    check("終端に居ても終了状態にならない",
          w.player.mediaStatus() != QMediaPlayer.MediaStatus.EndOfMedia,
          str(w.player.mediaStatus()))

    # 再生中に押すと一時停止してから移動する
    w.player.setPosition(1000)
    pump(400)
    w.player.play()
    check("再生を開始", wait_until(
        lambda: w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState,
        3000))
    check("再生中の一時停止＋移動", w.step_frame(1) is True)
    check("一時停止する", wait_until(
        lambda: w.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState, 3000))
    check("再生中でも位置が進む", pos_now(w) > 1000, str(pos_now(w)))

    # キー (アクション経由) でも動く
    w.player.setPosition(1500)
    pump(500)
    QTest.keyClick(w, Qt.Key.Key_Period)
    check(". キーで進む (1 回だけ)", wait_until(lambda: pos_now(w) == 1533, 3000),
          str(pos_now(w)))
    QTest.keyClick(w, Qt.Key.Key_Comma)
    check(", キーで戻る", wait_until(lambda: pos_now(w) == 1500, 3000),
          str(pos_now(w)))

    # --- 他の機能との相互作用 ---
    # (1) A-B リピートが有効でも、一時停止中のコマ送りは A へ戻されない
    #     (_maybe_ab_loop は再生中のみ働く)
    w.player.setPosition(1000)
    pump(500)
    check("A 点を設定できる", w.set_ab_a() is True)
    w.player.setPosition(1800)
    pump(600)
    check("B 点を設定できる", w.set_ab_b() is True, str(w.ab_state()))
    check("A-B 区間が有効", w.ab_active() is True, str(w.ab_state()))
    before = pos_now(w)
    check("A-B 中でもコマ送りできる", w.step_frame(-1) is True)
    check("A-B 中でも A へ飛ばされない",
          wait_until(lambda: pos_now(w) == before - 33, 3000), str(pos_now(w)))
    w.clear_ab()
    check("A-B を解除", w.ab_state() == (None, None), str(w.ab_state()))

    # (2) 再生中に押したときの一時停止位置がレジュームに残る
    #     (長さ 60 秒の動画でないと保存対象にならない)
    w._resume = {}
    check("長い動画をロード", w.load(LONG))
    check("長さを取得", wait_until(lambda: w.player.duration() > 0, 5000))
    w.player.setPosition(20000)
    pump(600)
    w.player.play()
    check("再生を開始", wait_until(
        lambda: w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState,
        3000))
    check("再生中のコマ送りは一時停止する", w.step_frame(1) is True)
    check("一時停止した", wait_until(
        lambda: w.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState,
        3000))
    saved = w._resume_pos_for(LONG)
    check("一時停止した位置が記憶される", saved is not None, str(w._resume))
    check("記憶した位置が現在位置と大きくずれない",
          saved is not None and abs(saved - w.player.position()) <= 500,
          f"{saved} vs {w.player.position()}")

    # --- ドキュメント / ヘルプ ---
    keys = [k for k, _ in SHORTCUTS]
    check("ヘルプに , / . を掲載", ", / ." in keys, str(keys))
    check("ヒントにフレーム送りの説明がある",
          any("1 フレーム" in n for n in HELP_NOTES), str(HELP_NOTES))
    check("ヒントにプロパティの説明がある",
          any("プロパティ" in n for n in HELP_NOTES), str(HELP_NOTES))
    readme = open(os.path.join(BASE, "README.md"), encoding="utf-8").read()
    check("README にフレーム送りの記載がある", "1 フレーム" in readme)
    check("README にプロパティの記載がある", "プロパティ" in readme)

    w.player.pause()
    w.close()
    if os.path.isfile(RESUME):
        os.remove(RESUME)
    shutil.rmtree(TMP, ignore_errors=True)
    return finish("P30framestep")


if __name__ == "__main__":
    sys.exit(main())
