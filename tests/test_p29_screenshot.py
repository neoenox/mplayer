"""P29: スクリーンショット保存 (Ctrl+S / 保存先を選ぶ / 失敗時 / 拡張子 / ヘルプ)。

- 保存先既定は動画と同じフォルダの「動画名_日時.png」
- 実ファイルが PNG として開けること・寸法が映像と一致すること
- 動画なし・保存先不正でも落ちないこと (状態表示にメッセージ)
- 別の動画を開くと保持フレームを破棄すること
"""
import glob
import os
import shutil
import sys
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(BASE, "tmp_p29")
SESSION = os.path.join(TMP, "session.json")
RESUME = os.path.join(BASE, "resume.json")
CLIP = os.path.join(TMP, "clip.mp4")
CLIP2 = os.path.join(TMP, "clip2.mp4")

shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(TMP, exist_ok=True)
os.environ["MPLAYER_SESSION_FILE"] = SESSION
if os.path.isfile(RESUME):
    os.remove(RESUME)

from helpers import (check, finish, first_bytes, make_app,  # noqa: E402
                     patch_message_boxes, silence, wait_for_frame, wait_until)

from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QMenu

import main as player_main
from main import HELP_NOTES, SHORTCUTS, PlayerWindow

SRC = os.path.join(BASE, "test_640x360.mp4")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def pump(ms=0):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def png_files():
    return sorted(glob.glob(os.path.join(TMP, "*.png")))


def main():
    patch_message_boxes()
    make_app()
    shutil.copyfile(SRC, CLIP)
    shutil.copyfile(SRC, CLIP2)

    w = PlayerWindow()
    w.show()
    silence(w)
    w._resume = {}

    # --- 構造 (アクション / メニュー / 表示) ---
    check("Ctrl+S が割当", w.shot_act.shortcut().toString() == "Ctrl+S",
          w.shot_act.shortcut().toString())
    check("Ctrl+S はウィンドウ全体で有効",
          w.shot_act.shortcutContext() == Qt.ShortcutContext.WindowShortcut,
          str(w.shot_act.shortcutContext()))
    menus = {m.title(): m for m in w.menuBar().findChildren(QMenu)}
    labels = [a.text() for a in menus["ファイル"].actions()] if "ファイル" in menus else []
    check("ファイルメニューに保存項目がある",
          any("スクリーンショットを保存" == x for x in labels), str(labels))
    check("ファイルメニューに名前を付けて保存がある",
          any("名前を付けて保存" in x for x in labels), str(labels))
    check("初期状態はメッセージ非表示", not w.shot_label.isVisible())
    check("初期状態はフレーム未保持", not w.has_frame())

    # --- 動画なし ---
    check("未ロードの既定保存先は無し", w.default_screenshot_path() is None)
    check("未ロードの保存は失敗 (None)", w.screenshot() is None)
    check("未ロードでもメッセージが出る", w.shot_label.isVisible(),
          w.shot_label.text())
    check("未ロードのメッセージ内容", "動画" in w.shot_label.text(),
          w.shot_label.text())
    check("未ロードで画像も取得できない", w.screenshot_image() is None)
    check("未ロードでファイルは作られない", png_files() == [], str(png_files()))
    w._clear_shot_message()

    # --- ロードしてフレームを取得 ---
    check("動画をロード", w.load(CLIP))
    check("長さを取得", wait_until(lambda: w.player.duration() > 0, 5000),
          str(w.player.duration()))
    # 再生中に最初のフレームが届く (一時停止したままだと届かないことがある)。
    check("フレームを取得できる", wait_for_frame(w))
    img = w.screenshot_image()
    check("QImage が返る", isinstance(img, QImage), str(type(img)))
    check("画像は空でない", img is not None and not img.isNull())
    check("画像の寸法が映像と一致 (640x360)",
          img is not None and (img.width(), img.height()) == (640, 360),
          f"{img.width()}x{img.height()}" if img is not None else "n/a")
    # 以降の保存検証は保持済みフレームを使うので、負荷を下げて一時停止する。
    w.player.pause()

    # --- 既定の保存先 ---
    default = w.default_screenshot_path()
    check("既定の保存先は動画と同じフォルダ",
          bool(default) and os.path.dirname(default) == TMP, str(default))
    check("既定の名前は動画名を含む",
          bool(default) and os.path.basename(default).startswith("clip_"),
          str(default))
    check("既定の拡張子は .png", bool(default) and default.endswith(".png"),
          str(default))

    saved = w.screenshot()
    check("既定の保存先へ保存できる", bool(saved) and os.path.isfile(saved),
          str(saved))
    check("保存先は既定と一致", saved == default, f"{saved} / {default}")
    check("保存されたファイルは 1KB 以上",
          bool(saved) and os.path.getsize(saved) > 1024,
          str(os.path.getsize(saved) if saved else 0))
    # 保存に失敗しても (フレーム未取得など) クラッシュさせず FAIL として集計する。
    check("PNG 署名で始まる", first_bytes(saved) == PNG_MAGIC, str(saved))
    reopened = QImage(saved) if saved else QImage()
    check("保存した PNG を開ける", not reopened.isNull())
    check("保存した PNG の寸法が一致",
          (reopened.width(), reopened.height()) == (640, 360),
          f"{reopened.width()}x{reopened.height()}")
    check("メッセージにファイル名が出る",
          bool(saved) and os.path.basename(saved) in w.shot_label.text(),
          w.shot_label.text())
    check("保存メッセージが表示される", w.shot_label.isVisible())

    # --- 同一秒に続けて保存しても上書きしない (連番) ---
    # 時刻に依存するため、strftime を固定して検証する。
    fixed = "20260101-000000"
    base = os.path.join(TMP, f"clip_{fixed}")
    with mock.patch.object(player_main.time, "strftime", lambda fmt: fixed):
        first = w.default_screenshot_path()
        check("既存が無ければ連番なし", first == base + ".png", str(first))
        open(base + ".png", "wb").write(b"dummy")
        second = w.default_screenshot_path()
        check("既存があれば _2 を返す", second == base + "_2.png", str(second))
        open(base + "_2.png", "wb").write(b"dummy")
        third = w.default_screenshot_path()
        check("さらに既存があれば _3 を返す", third == base + "_3.png", str(third))
        check("連番の候補は実在しない", third is not None and not os.path.exists(third))
    for dummy in (base + ".png", base + "_2.png"):
        os.remove(dummy)

    # --- 名前を付けて保存 (拡張子の補完・キャンセル) ---
    dialog_args = {}

    def fake_get_save(*args, **kwargs):
        dialog_args["args"] = args
        return os.path.join(TMP, "via_dialog"), "PNG 画像 (*.png)"

    saved_get_save = QFileDialog.getSaveFileName
    try:
        QFileDialog.getSaveFileName = fake_get_save
        w.screenshot_dialog()
        check("ダイアログの既定保存先が動画フォルダ",
              len(dialog_args.get("args", ())) >= 3 and
              os.path.dirname(dialog_args["args"][2]) == TMP,
              str(dialog_args.get("args")))
        check("ダイアログ経由で保存できる (拡張子を補完)",
              os.path.isfile(os.path.join(TMP, "via_dialog.png")))
        check("ダイアログ保存も PNG",
              first_bytes(os.path.join(TMP, "via_dialog.png")) == PNG_MAGIC)

        # .png 以外を入力したときは .png を足す (foo.jpg -> foo.jpg.png)
        QFileDialog.getSaveFileName = staticmethod(
            lambda *a, **k: (os.path.join(TMP, "typed.jpg"), ""))
        w.screenshot_dialog()
        check("拡張子が .png 以外でも .png を付ける",
              os.path.isfile(os.path.join(TMP, "typed.jpg.png")))

        QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
        before_cancel = len(png_files())
        w.screenshot_dialog()
        check("キャンセルでは保存されない", len(png_files()) == before_cancel,
              f"{before_cancel} -> {len(png_files())}")
    finally:
        QFileDialog.getSaveFileName = saved_get_save

    explicit = os.path.join(TMP, "explicit")
    check("明示パスへ保存できる", w.screenshot(explicit + ".png") == explicit + ".png"
          and os.path.isfile(explicit + ".png"))
    check("明示保存も PNG", first_bytes(explicit + ".png") == PNG_MAGIC)

    # --- 失敗しても落ちない ---
    bad = os.path.join(TMP, "no_such_dir", "x.png")
    check("保存できない場所では None", w.screenshot(bad) is None)
    check("失敗メッセージが出る", "失敗" in w.shot_label.text(), w.shot_label.text())
    check("失敗時はファイルが作られない", not os.path.exists(bad))

    # --- 映像が出ていないときの保存 ---
    # 環境により最初のフレームが届かないことがあるため、その経路を強制的に
    # 作って「保存せずメッセージを出すだけ」で落ちないことを確かめる。
    before_no_frame = len(png_files())
    w.screenshot_image = lambda: None
    try:
        check("映像なしの保存は None", w.screenshot() is None)
        check("映像なしのメッセージ", "映像" in w.shot_label.text(),
              w.shot_label.text())
        check("映像なしではファイルを作らない",
              len(png_files()) == before_no_frame,
              f"{before_no_frame} -> {len(png_files())}")
        check("映像なしの明示保存も None",
              w.screenshot(os.path.join(TMP, "no_frame.png")) is None)
        check("映像なしでは明示先も作られない",
              not os.path.exists(os.path.join(TMP, "no_frame.png")))
    finally:
        try:
            del w.screenshot_image
        except AttributeError:
            pass
    # テスト側のヘルパーも None / 不在パスで落ちないこと
    check("先頭バイト取得 (パスなし) は None", first_bytes(None) is None)
    check("先頭バイト取得 (存在しないパス) は None",
          first_bytes(os.path.join(TMP, "no_such.png")) is None)

    # --- メッセージは数秒で消える ---
    w._shot_hide_ms = 300
    w.screenshot()
    check("時間経過でメッセージが消える",
          wait_until(lambda: not w.shot_label.isVisible(), 3000),
          w.shot_label.text())
    check("消えたあとは文言も消える", w.shot_label.text() == "", w.shot_label.text())

    # --- Ctrl+S キー (1回だけ発火して保存される) ---
    fired = {"n": 0}
    w.shot_act.triggered.connect(lambda: fired.__setitem__("n", fired["n"] + 1))
    before = len(png_files())
    QTest.keyClick(w, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    pump(150)
    check("Ctrl+S が1回だけ発火", fired["n"] == 1, str(fired["n"]))
    check("Ctrl+S で保存される",
          wait_until(lambda: len(png_files()) >= before + 1, 3000),
          f"{before} -> {len(png_files())}")

    # --- 一時停止中にシークしたら、その位置の絵に更新される ---
    check("一時停止する", wait_until(
        lambda: w.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState,
        3000))
    before_img = w.screenshot_image()
    check("一時停止中も画像を保持している", before_img is not None)
    w.player.setPosition(max(1000, w.player.duration() - 300))
    check("一時停止中のシークで絵が更新される",
          wait_until(lambda: w.screenshot_image() is not before_img, 5000))
    after_img = w.screenshot_image()
    check("更新後の画像も空でない", after_img is not None and not after_img.isNull())
    check("シーク前とは別の絵になっている", after_img != before_img)

    # --- 全画面でも保存できる ---
    w.toggle_fullscreen()
    pump(60)
    check("全画面へ入る", w._is_fullscreen is True)
    before_fs = len(png_files())
    QTest.keyClick(w, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    check("全画面でも Ctrl+S で保存できる",
          wait_until(lambda: len(png_files()) >= before_fs + 1, 3000),
          f"{before_fs} -> {len(png_files())}")
    # 全画面で操作系が隠れていても、保存メッセージのために表示し直す。
    w._hide_fs_controls()
    check("全画面の操作系を隠せる", not w.controls.isVisible())
    w.screenshot()
    check("保存時に操作系が表示される", w.controls.isVisible())
    check("保存メッセージが見える", w.shot_label.isVisible())

    # 操作系を隠すタイマー (既定 2.5 秒) が先に切れても、メッセージの表示時間
    # (既定 3 秒) までは操作系ごと消えないこと。
    w._fs_hide_ms = 200
    w._shot_hide_ms = 1200
    w._hide_fs_controls()
    w.screenshot()
    pump(600)
    check("操作系を隠すタイマーより後に消える",
          w.shot_label.isVisible() and w.controls.isVisible(),
          f"label={w.shot_label.isVisible()} controls={w.controls.isVisible()}")
    check("メッセージは時間が来れば消える",
          wait_until(lambda: not w.shot_label.isVisible(), 3000))
    w._fs_hide_ms = 2500
    w._shot_hide_ms = 3000

    w.exit_fullscreen()
    pump(60)
    check("全画面を解除", w._is_fullscreen is False)

    # --- 別の動画を開くとフレームを破棄する ---
    check("別の動画を開く", w.load(CLIP2))
    check("開いた直後はフレームを保持しない", not w.has_frame())
    check("新しい動画でもフレームを取得できる", wait_for_frame(w))

    # --- ドキュメント / ヘルプ ---
    keys = [k for k, _ in SHORTCUTS]
    check("ヘルプに Ctrl+S を掲載", "Ctrl+S" in keys, str(keys))
    check("ヒントにスクリーンショットの説明がある",
          any("スクリーンショット" in n for n in HELP_NOTES), str(HELP_NOTES))
    readme = open(os.path.join(BASE, "README.md"), encoding="utf-8").read()
    check("README にスクリーンショットの記載がある", "スクリーンショット" in readme)
    check("README に Ctrl+S の記載がある", "Ctrl+S" in readme)

    w.player.pause()
    w.close()
    if os.path.isfile(RESUME):
        os.remove(RESUME)
    shutil.rmtree(TMP, ignore_errors=True)
    return finish("P29screenshot")


if __name__ == "__main__":
    sys.exit(main())
