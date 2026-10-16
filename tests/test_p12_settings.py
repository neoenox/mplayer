"""P12: セッション永続化 (音量/ミュート/速度/プレイリスト) の検証。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, patch_message_boxes, silence, wait_until

import main as app_main
from main import PlayerWindow

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO_A = os.path.join(BASE, "test_640x360.mp4")
VIDEO_B = os.path.join(BASE, "test_silent.mp4")


def main():
    patch_message_boxes()
    session = app_main.SESSION_FILE
    if os.path.isfile(session):
        os.remove(session)

    app = make_app()
    app.setQuitOnLastWindowClosed(False)

    # --- 保存 ---
    w1 = PlayerWindow()
    w1.show()
    w1.vol.setValue(35)
    w1.mute_btn.setChecked(True)
    w1.audio.setMuted(True)
    w1._rate_idx = 2  # 1.5x
    w1.player.setPlaybackRate(1.5)
    w1.speed_btn.setText("速度 1.5x")
    check("playlist added", w1.add_to_playlist([VIDEO_A, VIDEO_B]) == 2)
    w1.close()
    check("session file written on close", os.path.isfile(session))

    raw = json.load(open(session, encoding="utf-8"))
    check("saved volume", raw.get("volume") == 35, f"{raw.get('volume')}")
    check("saved muted", raw.get("muted") is True, f"{raw.get('muted')}")
    check("saved rate", raw.get("rate") == 1.5, f"{raw.get('rate')}")
    check("saved playlist", len(raw.get("playlist", [])) == 2,
          f"{raw.get('playlist')}")

    # --- 復元 ---
    w2 = PlayerWindow()
    w2.show()
    check("restore: default volume before", w2.vol.value() == 80, f"{w2.vol.value()}")
    w2.restore_session()
    check("restore volume", w2.vol.value() == 35, f"{w2.vol.value()}")
    check("restore muted", w2.mute_btn.isChecked() is True)
    check("restore rate", w2._rates[w2._rate_idx] == 1.5)
    check("restore rate button", w2.speed_btn.text() == "速度 1.5x")
    check("restore playlist count", wait_until(lambda: w2.playlist.count() == 2, 3000),
          f"count={w2.playlist.count()}")
    check("restore playlist path",
          os.path.abspath(VIDEO_A) == w2.playlist.item(0).data(app_main.Qt.ItemDataRole.UserRole))
    silence(w2)
    w2.close()

    # --- 壊れた / 不在ファイルは既定値 ---
    with open(session, "w", encoding="utf-8") as f:
        f.write("{ this is not json")
    w3 = PlayerWindow()
    w3.show()
    w3.restore_session()
    check("corrupt session -> default volume", w3.vol.value() == 80, f"{w3.vol.value()}")
    check("corrupt session -> empty playlist", w3.playlist.count() == 0)
    check("corrupt session -> default rate", w3._rates[w3._rate_idx] == 1.0)
    silence(w3)
    w3.close()

    os.remove(session)
    check("no crash when session missing", not os.path.isfile(session))
    w4 = PlayerWindow()
    w4.show()
    w4.restore_session()
    check("missing session -> default volume", w4.vol.value() == 80, f"{w4.vol.value()}")
    silence(w4)
    w4.close()

    return finish("P12settings")


if __name__ == "__main__":
    sys.exit(main())
