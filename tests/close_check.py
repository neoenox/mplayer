"""再生中にウィンドウを閉じてアプリが正常終了できるかの確認用。

使い方: 別プロセスで起動し、3秒再生後にウィンドウを閉じる。
8秒の番兵で os._exit(3) する。exit 0 = 正常終了、3 = 終了処理ハング。
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
w.vol.setValue(0)  # 検証中は無音
w.load(os.path.join(BASE, "test_640x360.mp4"))
QTimer.singleShot(3000, w.close)
QTimer.singleShot(8000, lambda: os._exit(3))
sys.exit(app.exec())
