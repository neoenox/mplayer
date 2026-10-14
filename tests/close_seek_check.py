"""予約シーク直後にウィンドウを閉じて正常終了できるかの確認用。

exit 0 = 正常終了、3 = 終了処理ハング (番兵)。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from main import PlayerWindow

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = QApplication(sys.argv)
w = PlayerWindow()
w.show()
w.vol.setValue(0)  # 無音
w.load(os.path.join(BASE, "test_640x360.mp4"))
QTimer.singleShot(2000, lambda: (w.seek.setValue(4400), w.seek_released()))
QTimer.singleShot(2100, w.close)  # 予約シークの直後に閉じる
QTimer.singleShot(8000, lambda: os._exit(3))
sys.exit(app.exec())
