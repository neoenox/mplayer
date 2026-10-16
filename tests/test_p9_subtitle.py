"""P9: 字幕 (SRT) パース・読み込み・表示・合成の検証。"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, patch_message_boxes, silence, wait_until

from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest

from main import PlayerWindow, parse_srt

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO = os.path.join(BASE, "test_640x360.mp4")

SAMPLE = (
    "\ufeff1\r\n"
    "00:00:01,000 --> 00:00:02,000\r\n"
    "Hello\r\nWorld\r\n"
    "\r\n"
    "2\r\n"
    "00:00:03.000 --> 00:00:04.000 X1:0 Y1:0\r\n"
    "Second\r\n"
    "\r\n"
    "garbage block no timestamp\r\n"
    "\r\n"
    "3\r\n"
    "not-a-time --> also-bad\r\n"
    "Ignored\r\n"
)


def unit_checks():
    cues = parse_srt(SAMPLE)
    check("parse count", len(cues) == 2, f"cues={cues}")
    check("parse first cue", cues[0] == (1000, 2000, "Hello\nWorld"), f"{cues[0]}")
    check("parse multiline body", cues[0][2] == "Hello\nWorld")
    check("parse dot-ms and coord suffix", cues[1][0] == 3000 and cues[1][1] == 4000,
          f"{cues[1]}")
    check("parse skips malformed", all(c[2] != "Ignored" for c in cues))
    check("parse empty", parse_srt("") == [])
    check("parse no-timestamp", parse_srt("hello\nworld\n") == [])


def grab(w):
    return w.screen().grabWindow(int(w.winId())).toImage()


def bottom_band_diff(img_a, img_b):
    """下端バンドの画素差分を数える (映像上に描画されている証拠)。"""
    hh = min(img_a.height(), img_b.height())
    ww = min(img_a.width(), img_b.width())
    if ww == 0 or hh == 0:
        return -1
    n = 0
    for y in range(int(hh * 0.86), hh, 2):
        for x in range(0, ww, 2):
            a, b = img_a.pixelColor(x, y), img_b.pixelColor(x, y)
            if (abs(a.red() - b.red()) > 30 or abs(a.green() - b.green()) > 30
                    or abs(a.blue() - b.blue()) > 30):
                n += 1
    return n


def main():
    patch_message_boxes()
    unit_checks()

    app = make_app()
    w = PlayerWindow()
    w.show()
    silence(w)
    w.load(VIDEO)
    check("video loaded", wait_until(lambda: w.player.duration() > 4000, 10000))
    w.player.pause()
    QTest.qWait(300)

    check("subs button enabled after load", w.subs_btn.isEnabled())
    check("no subtitle initially", w.subtitle_label.text() == "")

    srt = os.path.join(tempfile.gettempdir(), "mplayer_p9.srt")
    with open(srt, "w", encoding="utf-8") as f:
        f.write("1\n00:00:01,000 --> 00:00:02,000\nAAA\n\n"
                "2\n00:00:03,000 --> 00:00:04,000\nBBB\n")
    check("load_subtitles returns True", w.load_subtitles(srt) is True)
    check("subs button text ON", w.subs_btn.text() == "字幕 ON")

    w.player.setPosition(1500)
    check("cue A shown", wait_until(lambda: w.subtitle_label.text() == "AAA", 3000),
          f"text={w.subtitle_label.text()!r}")
    w.player.setPosition(3500)
    check("cue B shown", wait_until(lambda: w.subtitle_label.text() == "BBB", 3000),
          f"text={w.subtitle_label.text()!r}")
    w.player.setPosition(2500)
    check("gap hides subtitle", wait_until(lambda: w.subtitle_label.text() == "", 3000),
          f"text={w.subtitle_label.text()!r}")

    # ON/OFF 切替 (実ボタンクリック経路)
    w.player.setPosition(1500)
    wait_until(lambda: w.subtitle_label.text() == "AAA", 3000)
    w.subs_btn.click()
    check("toggle off clears", w.subtitle_label.text() == "", f"text={w.subtitle_label.text()!r}")
    check("toggle off unchecks button", w.subs_btn.isChecked() is False)
    w.subs_btn.click()
    check("toggle on restores", wait_until(lambda: w.subtitle_label.text() == "AAA", 3000))

    # 映像との合成 (ネイティブのみ; offscreen では grab 不可)
    if os.environ.get("QT_QPA_PLATFORM", "") != "offscreen":
        QTest.qWait(500)
        img_on = grab(w)
        w.subs_btn.click()
        QTest.qWait(500)
        img_off = grab(w)
        w.subs_btn.click()
        diff = bottom_band_diff(img_on, img_off)
        check("subtitle composited over video", diff > 50, f"diff={diff}")
    else:
        check("subtitle composited over video", True, "(skipped: offscreen)")

    # 破損・不正ファイル
    bad = os.path.join(tempfile.gettempdir(), "mplayer_p9_bad.srt")
    with open(bad, "w", encoding="utf-8") as f:
        f.write("no timestamps at all\njust text\n")
    check("invalid srt returns False", w.load_subtitles(bad) is False)
    check("invalid srt clears label", w.subtitle_label.text() == "")
    check("nonexistent srt returns False",
          w.load_subtitles(os.path.join(tempfile.gettempdir(), "nope_missing.srt")) is False)
    for p in (srt, bad):
        if os.path.isfile(p):
            os.remove(p)
    w.close()
    return finish("P9subtitle")


if __name__ == "__main__":
    sys.exit(main())
