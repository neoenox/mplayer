"""P39: 新版UIのレイアウト (空状態案内・時刻表示) の検証。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, pump, silence

from PySide6.QtCore import QUrl
from main import PlayerWindow

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO = os.path.join(BASE, "test_60s.mp4")


def centered(w):
    """案内が映像領域の中央・内側にあるか。"""
    v, h = w.video.rect(), w.empty_hint.geometry()
    return (abs(v.center().x() - h.center().x()) <= 2
            and abs(v.center().y() - h.center().y()) <= 2
            and v.contains(h))


def main():
    app = make_app()
    app.setQuitOnLastWindowClosed(False)
    w = PlayerWindow()
    w.resize(1100, 700)
    w.show()
    pump(150)

    check("空状態の案内が表示される", w.empty_layer.isVisible())
    check("案内レイヤーが映像領域に追従",
          w.empty_layer.geometry() == w.video.rect(),
          f"layer={w.empty_layer.geometry()} video={w.video.rect()}")
    check("案内が中央に配置される", centered(w))

    w.resize(760, 520)
    pump(150)
    check("リサイズ後も映像領域に追従",
          w.empty_layer.geometry() == w.video.rect(),
          f"layer={w.empty_layer.geometry()} video={w.video.rect()}")
    check("リサイズ後も中央に配置される", centered(w))

    w.player.setSource(QUrl.fromLocalFile(VIDEO))
    w._update_empty_state()
    pump(50)
    check("動画を開くと案内が消える", not w.empty_layer.isVisible())

    w._sync_time_labels(1000, 60000)
    check("残り時間を表示", w.time_label.text().startswith("00:01 / 01:00")
          and w.remaining_label.text() == "-00:59",
          f"{w.time_label.text()} / {w.remaining_label.text()}")
    w._sync_time_labels(0, 60000, ended=True)
    check("終了時は残り時間を隠す", "(終了)" in w.time_label.text()
          and w.remaining_label.text() == "—",
          f"{w.time_label.text()} / {w.remaining_label.text()}")

    silence(w)
    w.close()
    return finish("P39ui_layout")


if __name__ == "__main__":
    sys.exit(main())
