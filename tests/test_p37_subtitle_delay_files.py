"""P37: 字幕の遅延を動画ごとに記憶する。

- 遅延を動画 (パス) ごとに覚え、開いたときにその値へ切り替える
- 遅延 0 に戻す (リセット) と、その動画の記憶も消える
- session.json の "subtitle_delay_files" に保存し、壊れた値は無視する
- 旧形式 (subtitle_delay_files なし) は従来どおり現在値だけ復元する
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(BASE, "tmp_p37")
SESSION = os.path.join(TMP, "session.json")
RESUME = os.path.join(BASE, "resume.json")

os.makedirs(TMP, exist_ok=True)
os.environ["MPLAYER_SESSION_FILE"] = SESSION
if os.path.isfile(RESUME):
    os.remove(RESUME)

from helpers import check, finish, make_app, patch_message_boxes, silence  # noqa: E402

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402

from main import (HELP_NOTES, SUB_DELAY_LIMIT_MS,  # noqa: E402
                  SUB_DELAY_MAX_ENTRIES, PlayerWindow, __version__,
                  remember_sub_delay, sanitize_sub_delay_map)

SRC = os.path.join(BASE, "test_640x360.mp4")
CLIP_A = os.path.join(TMP, "a.mp4")
CLIP_B = os.path.join(TMP, "b.mp4")

# 1-2 秒と 3-4 秒に字幕。遅延が効いているかを位置から判定する。
SRT_TEXT = (
    "1\n"
    "00:00:01,000 --> 00:00:02,000\n"
    "いち\n"
    "\n"
    "2\n"
    "00:00:03,000 --> 00:00:04,000\n"
    "さん\n"
)


def pump(ms=0):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def write_session(data):
    with open(SESSION, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def read_session():
    with open(SESSION, encoding="utf-8") as f:
        return json.load(f)


def new_window():
    w = PlayerWindow()
    w.show()
    silence(w)
    return w


def main():
    patch_message_boxes()

    a = os.path.abspath(CLIP_A)
    b = os.path.abspath(CLIP_B)

    # --- 保存値の検証 (純粋関数) ---
    check("dict でなければ空", sanitize_sub_delay_map(None) == {},
          str(sanitize_sub_delay_map(None)))
    check("リストは空", sanitize_sub_delay_map([1, 2]) == {})
    check("正常な値はそのまま", sanitize_sub_delay_map({"/a": 500}) == {"/a": 500})
    check("キーが文字列でないものは捨てる", sanitize_sub_delay_map({1: 500}) == {})
    check("値が整数でないものは捨てる", sanitize_sub_delay_map({"/a": "500"}) == {})
    check("真偽値は捨てる", sanitize_sub_delay_map({"/a": True}) == {})
    check("大きすぎる値は上限に丸める",
          sanitize_sub_delay_map({"/a": 99999}) == {"/a": SUB_DELAY_LIMIT_MS},
          str(sanitize_sub_delay_map({"/a": 99999})))
    check("負の大きすぎる値も丸める",
          sanitize_sub_delay_map({"/a": -99999}) == {"/a": -SUB_DELAY_LIMIT_MS})
    too_many = sanitize_sub_delay_map(
        {f"/{i}": 100 for i in range(SUB_DELAY_MAX_ENTRIES + 3)})
    check("上限を超えた件数は古い方から落とす",
          len(too_many) == SUB_DELAY_MAX_ENTRIES and "/0" not in too_many,
          f"{len(too_many)} 件")

    check("遅延を覚える", remember_sub_delay({}, "/a", 300) == {"/a": 300})
    check("同じファイルは上書きする", remember_sub_delay({"/a": 300}, "/a", 700) == {"/a": 700})
    check("0 に戻したら忘れる", remember_sub_delay({"/a": 300}, "/a", 0) == {})
    check("パスが無ければ何もしない",
          remember_sub_delay({"/a": 300}, None, 500) == {"/a": 300})
    check("最後に触ったものが末尾へ移る",
          list(remember_sub_delay({"/a": 1, "/b": 2}, "/a", 5)) == ["/b", "/a"],
          str(list(remember_sub_delay({"/a": 1, "/b": 2}, "/a", 5))))
    full = remember_sub_delay({f"/{i}": 1 for i in range(SUB_DELAY_MAX_ENTRIES)},
                              "/x", 5)
    check("上限を超えたら古い方から落とす",
          len(full) == SUB_DELAY_MAX_ENTRIES and "/0" not in full and full.get("/x") == 5,
          f"{len(full)} 件")
    original = {"/a": 1}
    remember_sub_delay(original, "/x", 5)
    check("元の辞書は書き換えない", original == {"/a": 1}, str(original))

    # --- 動画ごとの切り替え (実挙動) ---
    shutil.copyfile(SRC, CLIP_A)
    shutil.copyfile(SRC, CLIP_B)
    for clip in (CLIP_A, CLIP_B):
        with open(os.path.splitext(clip)[0] + ".srt", "w", encoding="utf-8") as f:
            f.write(SRT_TEXT)

    make_app()
    w = new_window()
    check("最初は 0 秒", w.sub_delay_ms() == 0, str(w.sub_delay_ms()))
    check("記憶は空", w._sub_delays == {}, str(w._sub_delays))

    check("A を開ける", w.load(CLIP_A))
    check("開いた直後は 0 秒", w.sub_delay_ms() == 0, str(w.sub_delay_ms()))
    check("字幕が読み込まれる", len(w._cues) == 2, str(len(w._cues)))
    check("A を +1.5 秒にできる", w.set_sub_delay(1500) == 1500, str(w.sub_delay_ms()))
    check("A の遅延として覚える", w._sub_delays.get(a) == 1500, str(w._sub_delays))
    check("遅らせると字幕の出方がずれる", w._cue_text_at(2500) == "いち",
          repr(w._cue_text_at(2500)))

    check("B を開ける", w.load(CLIP_B))
    check("B は 0 秒から始まる", w.sub_delay_ms() == 0, str(w.sub_delay_ms()))
    check("メニューの表示も 0 秒", "0 秒" in w.sub_delay_info_act.text(),
          w.sub_delay_info_act.text())
    check("A の記憶は残っている", w._sub_delays.get(a) == 1500, str(w._sub_delays))
    check("ずれていないので出ない", w._cue_text_at(2500) == "", repr(w._cue_text_at(2500)))
    check("B を -0.2 秒にできる", w.set_sub_delay(-200) == -200, str(w.sub_delay_ms()))
    check("B の遅延として覚える", w._sub_delays.get(b) == -200, str(w._sub_delays))

    check("A を開き直せる", w.load(CLIP_A))
    check("A の遅延が戻る", w.sub_delay_ms() == 1500, str(w.sub_delay_ms()))
    check("メニューにも出る", "1.5" in w.sub_delay_info_act.text(),
          w.sub_delay_info_act.text())
    check("B の記憶も残っている", w._sub_delays.get(b) == -200, str(w._sub_delays))

    check("B をもう一度開ける", w.load(CLIP_B))
    check("B の遅延も戻る", w.sub_delay_ms() == -200, str(w.sub_delay_ms()))

    # --- リセットで記憶も消える ---
    check("リセットできる", w.reset_sub_delay() is None and w.sub_delay_ms() == 0)
    check("リセットで記憶が消える", b not in w._sub_delays, str(w._sub_delays))
    check("B を開き直す", w.load(CLIP_B))
    check("0 秒のまま (記憶していない)", w.sub_delay_ms() == 0, str(w.sub_delay_ms()))
    check("A の記憶は無事", w._sub_delays.get(a) == 1500, str(w._sub_delays))

    # --- 保存 ---
    w.load(CLIP_A)
    w.set_sub_delay(700)
    w._save_session()
    saved = read_session()
    check("session.json に保存する", saved.get("subtitle_delay_files", {}).get(a) == 700,
          str(saved.get("subtitle_delay_files")))
    check("現在値も従来どおり保存する", saved.get("subtitle_delay_ms") == 700,
          str(saved.get("subtitle_delay_ms")))
    check("上限の件数で保存する",
          len(saved.get("subtitle_delay_files", {})) <= SUB_DELAY_MAX_ENTRIES)

    # --- 実際に保存した session.json をそのまま復元する ---
    w_round = new_window()
    w_round.restore_session()
    check("保存値が現在値として復元される", w_round.sub_delay_ms() == 700,
          str(w_round.sub_delay_ms()))
    check("開いた動画に保存値が適用される",
          w_round.load(CLIP_A) is True and w_round.sub_delay_ms() == 700,
          str(w_round.sub_delay_ms()))
    w_round.close()

    # --- 復元 (壊れた値は無視する) ---
    write_session({"subtitle_delay_files": {"x": "1", a: 400, "y": True}})
    w2 = new_window()
    w2.restore_session()
    check("壊れた値は無視して戻す", w2._sub_delays == {a: 400}, str(w2._sub_delays))
    check("開いたときに適用する", w2.load(CLIP_A) is True and w2.sub_delay_ms() == 400,
          str(w2.sub_delay_ms()))
    w2.update_subtitle(2350)
    check("復元値で字幕がずれる", w2.subtitle_label.text() == "いち",
          repr(w2.subtitle_label.text()))
    check("メニューにも復元値が出る", "0.4" in w2.sub_delay_info_act.text(),
          w2.sub_delay_info_act.text())

    # --- 旧形式 (subtitle_delay_files なし) ---
    write_session({"subtitle_delay_ms": 800})
    w3 = new_window()
    w3.restore_session()
    check("現在値は従来どおり復元する", w3.sub_delay_ms() == 800, str(w3.sub_delay_ms()))
    check("記憶は空のまま", w3._sub_delays == {}, str(w3._sub_delays))
    check("ファイルを開くと 0 秒から", w3.load(CLIP_B) is True and w3.sub_delay_ms() == 0,
          str(w3.sub_delay_ms()))

    # --- ドキュメント ---
    with open(os.path.join(BASE, "README.md"), encoding="utf-8") as f:
        readme = f.read()
    check("README に動画ごとの字幕遅延", "字幕の遅延は動画ごと" in readme)
    with open(os.path.join(BASE, "CHANGELOG.md"), encoding="utf-8") as f:
        changelog = f.read()
    check("CHANGELOG に 1.25.0 (この機能を入れた版)", "## [1.25.0]" in changelog)
    check("CHANGELOG に字幕遅延の記載", "字幕の遅延を動画ごとに" in changelog)
    check("CHANGELOG に現行バージョンの節がある",
          f"## [{__version__}]" in changelog, __version__)
    check("ヒントに動画ごとの説明",
          any("字幕の遅延は動画ごと" in n for n in HELP_NOTES),
          str([n for n in HELP_NOTES if "遅延" in n]))

    for win in (w, w2, w3):
        win.close()
    pump(100)
    shutil.rmtree(TMP, ignore_errors=True)
    return finish("P37subdelayfiles")


if __name__ == "__main__":
    sys.exit(main())
