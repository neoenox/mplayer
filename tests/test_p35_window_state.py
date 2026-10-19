"""P35: ウィンドウの位置・サイズ・最大化・プレイリスト表示の記憶。

- session.json の "window" に 位置/サイズ/最大化/パネル表示 を保存する
- 起動時に復元する (最大化とパネル表示は show() の後に適用する)
- 画面外・壊れた値は既定 (960x600) にフォールバックする
- 全画面のまま終了しても、全画面に入る前の位置を保存する
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(BASE, "tmp_p35")
SESSION = os.path.join(TMP, "session.json")
RESUME = os.path.join(BASE, "resume.json")

os.makedirs(TMP, exist_ok=True)
os.environ["MPLAYER_SESSION_FILE"] = SESSION
if os.path.isfile(RESUME):
    os.remove(RESUME)

from helpers import check, finish, make_app, patch_message_boxes, silence  # noqa: E402

from PySide6.QtCore import QEventLoop, QRect, QTimer  # noqa: E402

from main import (HELP_NOTES, WINDOW_DEFAULT_H, WINDOW_DEFAULT_W,  # noqa: E402
                  WINDOW_MIN_H, WINDOW_MIN_VISIBLE_H, WINDOW_MIN_VISIBLE_W,
                  WINDOW_MIN_W, PlayerWindow, sanitize_window_rect, __version__)

# 復元に使う値。画面 (CI/オフスクリーンとも) に収まる小さめの値にする。
X, Y, W, H = 40, 30, 640, 440

KEYS = ["h", "maximized", "playlist_dock", "w", "x", "y"]


class FakeScreen:
    """availableGeometry() だけを持つ画面の代役 (純粋関数の検証用)。"""

    def __init__(self, rect):
        self._rect = rect

    def availableGeometry(self):
        return self._rect


def pump(ms=0):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def rect_of(w):
    return tuple(w.geometry().getRect())


def main():
    patch_message_boxes()
    make_app()
    big = [FakeScreen(QRect(0, 0, 1920, 1040))]
    dual = big + [FakeScreen(QRect(1920, 0, 1920, 1040))]

    # --- 検証ロジック (純粋関数) ---
    check("通常の位置・サイズはそのまま",
          sanitize_window_rect(120, 90, 800, 500, big) == (120, 90, 800, 500),
          str(sanitize_window_rect(120, 90, 800, 500, big)))
    check("小さすぎるサイズは下限に丸める",
          sanitize_window_rect(10, 10, 5, 5, big) == (10, 10, WINDOW_MIN_W, WINDOW_MIN_H),
          str(sanitize_window_rect(10, 10, 5, 5, big)))
    check("負のサイズも下限に丸める",
          sanitize_window_rect(0, 0, -100, -100, big) == (0, 0, WINDOW_MIN_W, WINDOW_MIN_H),
          str(sanitize_window_rect(0, 0, -100, -100, big)))
    check("大きすぎるサイズは画面に収める",
          sanitize_window_rect(0, 0, 5000, 5000, big) == (0, 0, 1920, 1040),
          str(sanitize_window_rect(0, 0, 5000, 5000, big)))
    check("画面外は拒否", sanitize_window_rect(99999, 99999, 800, 500, big) is None)
    check("負の座標も拒否", sanitize_window_rect(-5000, -5000, 800, 500, big) is None)
    check("少しはみ出す配置は許容",
          sanitize_window_rect(-700, 100, 800, 500, big) == (-700, 100, 800, 500),
          str(sanitize_window_rect(-700, 100, 800, 500, big)))
    check("別の画面に載っていれば許容",
          sanitize_window_rect(2000, 100, 800, 500, dual) == (2000, 100, 800, 500),
          str(sanitize_window_rect(2000, 100, 800, 500, dual)))
    check("文字列は拒否", sanitize_window_rect("120", 90, 800, 500, big) is None)
    check("小数は拒否", sanitize_window_rect(120.5, 90, 800, 500, big) is None)
    check("真偽値は拒否", sanitize_window_rect(True, 1, 800, 500, big) is None)
    check("None は拒否", sanitize_window_rect(None, None, None, None, big) is None)
    check("画面情報が無くても下限だけは適用",
          sanitize_window_rect(10, 10, 5, 5) == (10, 10, WINDOW_MIN_W, WINDOW_MIN_H),
          str(sanitize_window_rect(10, 10, 5, 5)))
    check("既定サイズは 960x600",
          (WINDOW_DEFAULT_W, WINDOW_DEFAULT_H) == (960, 600),
          f"{WINDOW_DEFAULT_W}x{WINDOW_DEFAULT_H}")
    check("下限は既定より小さい",
          WINDOW_MIN_W < WINDOW_DEFAULT_W and WINDOW_MIN_H < WINDOW_DEFAULT_H,
          f"{WINDOW_MIN_W}x{WINDOW_MIN_H}")

    # --- 保存する内容 ---
    w = PlayerWindow()
    check("保存用のキー", sorted(w.window_state_for_save()) == KEYS,
          str(sorted(w.window_state_for_save())))
    w.show()
    pump(150)
    silence(w)
    w._resume = {}
    w.setGeometry(X, Y, W, H)
    pump(50)
    st = w.window_state_for_save()
    check("位置とサイズが入る", (st["x"], st["y"], st["w"], st["h"]) == (X, Y, W, H),
          str(st))
    check("保存値は実測と一致", (st["x"], st["y"], st["w"], st["h"]) == rect_of(w),
          f"{st} / {rect_of(w)}")
    check("既定は最大化ではない", st["maximized"] is False)
    check("既定のパネルは閉じている", st["playlist_dock"] is False)
    w.pl_btn.setChecked(True)
    pump(50)
    check("パネルを開くと保存値も True", w.window_state_for_save()["playlist_dock"] is True)
    check("パネルを開いた状態でも実測と一致",
          (w.window_state_for_save()["x"], w.window_state_for_save()["w"]) ==
          (rect_of(w)[0], rect_of(w)[2]),
          f"{w.window_state_for_save()} / {rect_of(w)}")
    w.pl_btn.setChecked(False)
    pump(50)

    # --- 復元 (位置・サイズ) ---
    st = {"x": X, "y": Y, "w": W, "h": H, "maximized": False, "playlist_dock": False}
    w2 = PlayerWindow()
    check("復元前は既定サイズ", (w2.width(), w2.height()) == (960, 600),
          f"{w2.width()}x{w2.height()}")
    check("適用できた", w2.apply_window_state(st) is True)
    check("位置とサイズが復元される", rect_of(w2) == (X, Y, W, H), str(rect_of(w2)))
    check("最大化は予約されない", w2._pending_maximized is False)
    check("パネルは予約されない", w2._pending_dock is False)
    w2.show()
    pump(250)
    silence(w2)
    w2._resume = {}
    check("show 後も復元したサイズをおおむね保つ",
          abs(w2.width() - W) <= 30 and abs(w2.height() - H) <= 30,
          f"{w2.width()}x{w2.height()}")

    # --- 復元 (パネル表示) ---
    w3 = PlayerWindow()
    check("パネル付きの状態を適用",
          w3.apply_window_state(dict(st, playlist_dock=True)) is True)
    check("パネル表示が予約される", w3._pending_dock is True)
    check("適用直後はパネルを開かない (show 前)",
          w3.pl_dock.isVisible() is False and w3.pl_btn.isChecked() is False)
    check("show 前の位置は復元した値", rect_of(w3) == (X, Y, W, H), str(rect_of(w3)))
    w3.show()
    pump(250)
    silence(w3)
    w3._resume = {}
    check("show 後に予約が消える", w3._pending_dock is False)
    check("パネルが開く", w3.pl_dock.isVisible() is True)
    check("リストボタンも押された状態", w3.pl_btn.isChecked() is True)
    # ドックの最小幅でウィンドウは広がる (Qt のレイアウト制約)。画面内には残る。
    check("パネルを開いても画面内に残る",
          w3.x() > -WINDOW_MIN_VISIBLE_W and w3.y() > -WINDOW_MIN_VISIBLE_H,
          f"{w3.x()},{w3.y()}")

    # --- 壊れた値・画面外は既定のまま ---
    w4 = PlayerWindow()
    check("型が違う値は適用しない",
          w4.apply_window_state({"x": "a", "y": "b", "w": "c", "h": "d"}) is False)
    check("型が違うと予約もしない",
          (w4._pending_maximized, w4._pending_dock) == (False, False))
    check("拒否しても既定サイズのまま", (w4.width(), w4.height()) == (960, 600),
          f"{w4.width()}x{w4.height()}")
    check("画面外は適用しない",
          w4.apply_window_state({"x": 50000, "y": 50000, "w": W, "h": H}) is False)
    check("画面外でも既定サイズのまま", (w4.width(), w4.height()) == (960, 600))
    check("辞書でなければ無視", w4.apply_window_state("nope") is False)
    check("None でも落ちない", w4.apply_window_state(None) is False)
    check("項目が足りなくても落ちない", w4.apply_window_state({}) is False)
    w4._apply_session({"window": "nope"})
    check("_apply_session 経由でも壊れた値は無視",
          (w4.width(), w4.height()) == (960, 600), f"{w4.width()}x{w4.height()}")
    w4._apply_session({"window": {"x": "a", "y": 0, "w": W, "h": H}})
    check("_apply_session の不正値でも既定のまま",
          (w4.width(), w4.height()) == (960, 600) and w4._pending_dock is False)

    # --- 最大化 ---
    w5 = PlayerWindow()
    w5.show()
    pump(150)
    silence(w5)
    w5._resume = {}
    w5.setGeometry(X, Y, W, H)
    pump(50)
    w5.showMaximized()
    pump(250)
    check("最大化できる", w5.isMaximized() is True, str(w5.isMaximized()))
    st_max = w5.window_state_for_save()
    check("最大化中は通常時のサイズを保存",
          (st_max["w"], st_max["h"]) == (W, H), str((st_max["w"], st_max["h"])))
    check("最大化フラグを保存", st_max["maximized"] is True)
    w6 = PlayerWindow()
    check("最大化付きの状態を適用", w6.apply_window_state(st_max) is True)
    check("最大化が予約される", w6._pending_maximized is True)
    now = rect_of(w6)
    check("適用直後は最大化しない (show 前)", w6.isMaximized() is False, str(now))
    w6.show()
    pump(400)
    silence(w6)
    w6._resume = {}
    check("show 後に最大化される", w6.isMaximized() is True, str(w6.isMaximized()))
    check("予約は消える", w6._pending_maximized is False)
    check("通常時のサイズも残っている",
          (w6.normalGeometry().width(), w6.normalGeometry().height()) == (W, H),
          str(rect_of(w6)))
    w6.showNormal()
    pump(150)
    check("最大化を解除できる", w6.isMaximized() is False)

    # --- session.json 経由の往復 ---
    w.setGeometry(X, Y, W, H)
    w.pl_btn.setChecked(False)
    pump(50)
    w._save_session()
    with open(SESSION, encoding="utf-8") as f:
        data = json.load(f)
    check("session.json に window が入る", isinstance(data.get("window"), dict),
          str(type(data.get("window"))))
    win = data["window"]
    check("保存された位置とサイズ",
          (win.get("x"), win.get("y"), win.get("w"), win.get("h")) == (X, Y, W, H),
          str(win))
    check("保存されたフラグ",
          win.get("maximized") is False and win.get("playlist_dock") is False,
          str(win))
    w7 = PlayerWindow()
    check("復元前は既定サイズ", (w7.width(), w7.height()) == (960, 600))
    w7._apply_session(data)
    check("session 経由でも復元される", rect_of(w7) == (X, Y, W, H), str(rect_of(w7)))

    # --- 全画面のまま終了したとき ---
    # ドックを開いた状態で位置を決める (開くとウィンドウの最小幅が変わるため、
    # 実際の矩形を基準に検証する)。
    w.pl_btn.setChecked(True)
    pump(50)
    w.setGeometry(X, Y, W, H)
    pump(50)
    rect_fs = rect_of(w)
    w.toggle_fullscreen()
    pump(200)
    check("全画面に入る", w._is_fullscreen is True)
    check("全画面前の矩形を控える", w._fs_rect == rect_fs,
          f"{w._fs_rect} / {rect_fs}")
    st_fs = w.window_state_for_save()
    check("全画面中でも通常時の位置を保存",
          (st_fs["x"], st_fs["y"], st_fs["w"], st_fs["h"]) == rect_fs, str(st_fs))
    check("全画面中のパネル状態は全画面前の値", st_fs["playlist_dock"] is True)
    check("全画面中でも最大化は False", st_fs["maximized"] is False)
    w._save_session()
    with open(SESSION, encoding="utf-8") as f:
        saved_fs = json.load(f)["window"]
    check("全画面中に保存しても通常時の値",
          (saved_fs["x"], saved_fs["y"], saved_fs["w"], saved_fs["h"],
           saved_fs["playlist_dock"]) == rect_fs + (True,), str(saved_fs))
    w.exit_fullscreen()
    pump(200)
    check("全画面を抜ける", w._is_fullscreen is False)
    check("控えを破棄する", w._fs_rect is None)
    check("抜けた後は全画面前のパネル表示に戻る", w.pl_dock.isVisible() is True)

    # --- ドキュメント ---
    check("ヘルプにウィンドウの記憶の説明",
          any("ウィンドウ" in n for n in HELP_NOTES),
          str([n for n in HELP_NOTES if "ウィンドウ" in n]))
    with open(os.path.join(BASE, "README.md"), encoding="utf-8") as f:
        readme = f.read()
    check("README にウィンドウ位置の記憶", "ウィンドウ位置" in readme)
    check("README に画面外の説明", "画面外" in readme)
    with open(os.path.join(BASE, "CHANGELOG.md"), encoding="utf-8") as f:
        changelog = f.read()
    check("CHANGELOG に 1.23.0 (この機能を入れた版)", "## [1.23.0]" in changelog)
    check("CHANGELOG に現行バージョンの節がある",
          f"## [{__version__}]" in changelog, __version__)
    check("CHANGELOG にウィンドウの記載", "ウィンドウの位置" in changelog)

    # --- 後始末 ---
    for win in (w, w2, w3, w4, w5, w6, w7):
        try:
            win.close()
        except Exception:
            pass
    if os.path.isfile(RESUME):
        os.remove(RESUME)
    shutil.rmtree(TMP, ignore_errors=True)
    return finish("P35windowstate")


if __name__ == "__main__":
    sys.exit(main())
