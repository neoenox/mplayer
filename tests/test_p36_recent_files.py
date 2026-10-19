"""P36: 最近使ったファイル (履歴)。

- session.json の "recent" に直近 10 件を保存し、起動時に復元する
- 同じファイルは 1 つにまとめ、最後に開いたものが先頭に来る
- 消えたファイルは履歴から除く (起動時・保存時・開けなかったとき)
- メニュー (ファイル → 最近使ったファイル) から開ける
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(BASE, "tmp_p36")
SESSION = os.path.join(TMP, "session.json")
RESUME = os.path.join(BASE, "resume.json")

os.makedirs(TMP, exist_ok=True)
os.environ["MPLAYER_SESSION_FILE"] = SESSION
if os.path.isfile(RESUME):
    os.remove(RESUME)

from helpers import (check, dialog_calls, finish, make_app,  # noqa: E402
                     patch_message_boxes, silence)

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402

from main import (HELP_NOTES, RECENT_MAX, PlayerWindow, __version__,  # noqa: E402
                  recent_add, recent_key, recent_prune)

VIDEO = os.path.join(BASE, "test_640x360.mp4")
VIDEO2 = os.path.join(BASE, "test_silent.mp4")


def pump(ms=0):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def menu_paths(w):
    """メニューに出ているファイルのフルパス (項目の data) を順に返す。"""
    return [a.data() for a in w.recent_menu.actions() if a.data()]


def menu_names(w):
    """メニューに出ているファイル名を順に返す。"""
    return [a.text() for a in w.recent_menu.actions() if a.data()]


def write_session(recent):
    with open(SESSION, "w", encoding="utf-8") as f:
        json.dump({"recent": recent}, f, ensure_ascii=False)


def read_session():
    with open(SESSION, encoding="utf-8") as f:
        return json.load(f)


def main():
    patch_message_boxes()

    a = os.path.abspath(VIDEO)
    b = os.path.abspath(VIDEO2)
    # 実体の無いパス (履歴に入っていたが、あとで消えたファイルの代わり)
    gone = os.path.abspath(os.path.join(TMP, "gone.mp4"))

    # --- 履歴の組み立て (純粋関数) ---
    check("新しいパスは先頭に入る", recent_add([], a) == [a], str(recent_add([], a)))
    check("続けて開くと先頭が入れ替わる", recent_add([a], b) == [b, a],
          str(recent_add([a], b)))
    check("同じファイルを開き直しても増えない", recent_add([b, a], a) == [a, b],
          str(recent_add([b, a], a)))
    check("./ や .. の違いは同じファイルとみなす",
          recent_add([a], os.path.join(os.path.dirname(a), ".", os.path.basename(a))) == [a],
          str(recent_add([a], os.path.join(os.path.dirname(a), ".", os.path.basename(a)))))
    if os.path.normcase("A") == "a":  # Windows は大文字小文字を区別しない
        check("大文字小文字の違いも同じファイルとみなす",
              recent_add([a], a.upper()) == [a.upper()], str(recent_add([a], a.upper())))
    check("上限を超えると古い方から落とす",
          len(recent_add([f"p{i}" for i in range(30)], a)) == RECENT_MAX,
          str(len(recent_add([f"p{i}" for i in range(30)], a))))
    check("上限ちょうどは落とさない",
          recent_add([f"p{i}" for i in range(RECENT_MAX - 1)], a)[-1] == f"p{RECENT_MAX - 2}")
    check("文字列でない要素は無視する", recent_add([1, None, a], b) == [b, a],
          str(recent_add([1, None, a], b)))
    check("空のパスは追加しない", recent_add([a], "") == [a], str(recent_add([a], "")))
    check("キーは絶対パスから作る", recent_key(a) == os.path.normcase(a), recent_key(a))

    exists = lambda p: p != b  # noqa: E731 (テスト用の代役)
    check("存在しないファイルは外す", recent_prune([a, b, gone], exists) == [a, gone],
          str(recent_prune([a, b, gone], exists)))
    check("掃除しても順序は変わらない", recent_prune([gone, b, a], exists) == [gone, a])
    check("文字列でない要素も外す", recent_prune([1, a], exists) == [a])
    check("全部消えていれば空になる", recent_prune([b], exists) == [])

    # --- メニュー (空の状態) ---
    make_app()
    w = PlayerWindow()
    w.show()
    silence(w)

    check("メニューがある", w.recent_menu.title() == "最近使ったファイル",
          w.recent_menu.title())
    acts = w.recent_menu.actions()
    check("空のときは案内を 1 件だけ出す", len(acts) == 1, str(len(acts)))
    check("案内は押せない", acts and acts[0].isEnabled() is False)
    check("案内に「履歴」と出る", acts and "履歴" in acts[0].text(), acts[0].text())

    # --- 開くたびに履歴が伸びる ---
    check("1 本目を開ける", w.load(VIDEO))
    check("履歴が 1 件になる", w._recent == [a], str(w._recent))
    check("メニューにファイル名が出る", menu_names(w) == [os.path.basename(a)],
          str(menu_names(w)))
    check("メニューの項目にフルパスが入る", menu_paths(w) == [a], str(menu_paths(w)))
    check("クリアの項目が付く",
          [x.text() for x in w.recent_menu.actions() if not x.data()][-1:]
          == ["履歴をクリア"], str([x.text() for x in w.recent_menu.actions()]))

    check("2 本目を開ける", w.load(VIDEO2))
    check("新しい方が先頭に来る", w._recent == [b, a], str(w._recent))
    check("1 本目を開き直しても 2 件のまま", w.load(VIDEO) and w._recent == [a, b],
          str(w._recent))
    check("メニューの順も履歴と同じ", menu_paths(w) == [a, b], str(menu_paths(w)))

    # --- メニューから開く ---
    w.load(VIDEO2)
    act = [x for x in w.recent_menu.actions() if x.data() == a][0]
    act.trigger()
    pump(300)
    check("メニューから開ける", w._current_path == a, str(w._current_path))
    check("開いたファイルが先頭へ動く", w._recent[0] == a, str(w._recent))

    # --- 消えたファイル (履歴に残っているが実体が無い) ---
    w._recent = recent_add(w._recent, gone)
    w._refresh_recent_menu()
    check("実体の無いパスも履歴には入る", w._recent[0] == gone, str(w._recent))
    dialog_calls.clear()
    before = w._current_path
    w.open_recent(gone)
    check("消えたファイルは開かない", w._current_path == before, str(w._current_path))
    check("警告を出す", any("見つかりません" in str(call) for call in dialog_calls),
          str(dialog_calls))
    check("消えたファイルは履歴から外れる", gone not in w._recent, str(w._recent))
    check("残りは減っていない", a in w._recent and b in w._recent, str(w._recent))

    # --- クリア ---
    w.clear_recent()
    check("履歴をクリアできる", w._recent == [], str(w._recent))
    acts = w.recent_menu.actions()
    check("クリア後は案内だけになる", len(acts) == 1 and acts[0].isEnabled() is False,
          str([x.text() for x in acts]))

    # --- 保存 ---
    w._recent = [a, b]
    w._save_session()
    check("session.json に recent を書く", read_session().get("recent") == [a, b],
          str(read_session().get("recent")))
    w._recent = [a, gone]
    w._save_session()
    check("保存時に消えたファイルを掃除する", read_session().get("recent") == [a],
          str(read_session().get("recent")))

    # --- 復元 ---
    write_session([b, a, gone, 1, "x"])
    w2 = PlayerWindow()
    w2.show()
    silence(w2)
    w2.restore_session()
    check("起動時に履歴を戻す", w2._recent == [b, a], str(w2._recent))
    check("復元したメニューに出る", menu_paths(w2) == [b, a], str(menu_paths(w2)))
    check("消えたファイルは復元しない", gone not in w2._recent, str(w2._recent))

    many = []
    for i in range(RECENT_MAX + 2):
        p = os.path.join(TMP, f"many{i}.mp4")
        shutil.copyfile(VIDEO, p)
        many.append(p)
    write_session(many)
    w3 = PlayerWindow()
    w3.show()
    silence(w3)
    w3.restore_session()
    check("起動時に上限で切る", w3._recent == many[:RECENT_MAX],
          f"{len(w3._recent)} 件")
    check("上限の件数だけメニューに出る", len(menu_paths(w3)) == RECENT_MAX,
          str(len(menu_paths(w3))))

    # --- ドキュメント ---
    readme = open(os.path.join(BASE, "README.md"), encoding="utf-8").read()
    check("README に最近使ったファイルが載っている", "最近使ったファイル" in readme)
    changelog = open(os.path.join(BASE, "CHANGELOG.md"), encoding="utf-8").read()
    check("CHANGELOG に 1.24.0 (この機能を入れた版)", "## [1.24.0]" in changelog)
    check("CHANGELOG に最近使ったファイルの記載", "最近使ったファイル" in changelog)
    check("CHANGELOG に現行バージョンの節がある",
          f"## [{__version__}]" in changelog, __version__)
    check("ヒントに最近使ったファイルがある",
          any("最近使ったファイル" in n for n in HELP_NOTES), str(HELP_NOTES[-3:]))

    for win in (w, w2, w3):
        win.close()
    shutil.rmtree(TMP, ignore_errors=True)
    return finish("P36recentfiles")


if __name__ == "__main__":
    sys.exit(main())
