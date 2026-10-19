"""E2Eテスト共通ヘルパー (P1/P2用)。"""
import os
import sys

from PySide6.QtCore import QEventLoop, QTimer, Qt
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication, QMessageBox

# モーダルダイアログの記録 (パッチ適用後に格納)
dialog_calls = []


def patch_message_boxes():
    """QMessageBoxをGUIなし記録スタブに置換し、モーダル起因のハングを排除する。"""
    from PySide6.QtWidgets import QMessageBox as MB

    def fake(kind):
        def _f(*args, **kwargs):
            dialog_calls.append((kind, args[1] if len(args) > 1 else "", args[2] if len(args) > 2 else ""))
            return MB.StandardButton.Ok
        return _f

    MB.warning = staticmethod(fake("warning"))
    MB.information = staticmethod(fake("information"))
    MB.critical = staticmethod(fake("critical"))

passed = failed = skipped = 0


def check(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"[PASS] {name} {extra}", flush=True)
    else:
        failed += 1
        print(f"[FAIL] {name} {extra}", flush=True)


def skip(name, reason=""):
    global skipped
    skipped += 1
    print(f"[SKIP] {name} {reason}", flush=True)


def wait_until(pred, timeout_ms=10000, poll_ms=100):
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(poll_ms)
    state = {"done": False}

    def poll():
        try:
            if pred():
                state["done"] = True
                loop.quit()
        except Exception:
            pass

    timer.timeout.connect(poll)
    timer.start()
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    timer.stop()
    return state["done"]


def pump(ms=0):
    """ms ミリ秒だけイベントループを回す。"""
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def activate_window(w, timeout_ms=800, poll_ms=30):
    """ウィンドウを前面に出す (前面にできたら True)。

    ショートカットはアクティブなウィンドウにしか届かない。この環境では
    表示直後や時間経過のあとに OS 側のフォーカスが外れていることがあり、
    そのままキーを押しても黙って捨てられる (テストがまぐれで落ちる原因)。
    キーを押す前に前面へ戻すために使う。
    """
    try:
        if w.isActiveWindow():
            return True
        w.raise_()
        w.activateWindow()
        # WindowActive を立てると OS に前面化を要求できる (全画面/最大化は保つ)
        w.setWindowState(w.windowState() | Qt.WindowState.WindowActive)
    except Exception:
        return False
    return wait_until(w.isActiveWindow, timeout_ms, poll_ms)


def press_key(w, key, mods=None, cond=None, tries=3, wait_ms=120):
    """キーを押す (押す前にウィンドウを前面に出す)。

    cond を渡すと、その条件が満たされるまで押し直す。前面に無いときの
    キー入力は捨てられて状態が変わらないので、効くまで押し直しても
    二重発火にはならない (1 回で効けば 1 回で止まる)。「1 回のキー入力で
    1 回だけ発火する」ことを確かめるテストでは、cond に「効果が出たか」を
    渡してから、発火回数を別途検査する。
    """
    from PySide6.QtTest import QTest

    if mods is None:
        mods = Qt.KeyboardModifier.NoModifier
    for _ in range(max(1, tries)):
        activate_window(w)
        QTest.keyClick(w, key, mods)
        pump(wait_ms)
        if cond is None or cond():
            return True
    return False


def first_bytes(path, n=8):
    """ファイルの先頭 n バイト (開けない/存在しないときは None)。

    保存に失敗した場合でもテストがクラッシュせず FAIL として集計できるようにする。
    """
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            return f.read(n)
    except OSError:
        return None


def wait_for_frame(w, timeout_ms=7000, attempts=3, nudge_ms=200):
    """最初のフレームが届くまで待つ。届かないときは促して再試行する。

    デコーダの初期化タイミングにより、再生中でも最初のフレームが届かず
    タイムアウトすることがある (環境依存)。再生状態と位置を動かすと
    デコードが促されるため、数回試してから諦める。
    """
    for i in range(max(1, attempts)):
        if wait_until(lambda: w.screenshot_image() is not None, timeout_ms):
            return True
        try:
            if w.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                w.player.play()
            w.player.setPosition(w.player.position() + nudge_ms * (i + 1))
        except Exception:
            pass
    return False


def make_app():
    app = QApplication(sys.argv)
    _patch_key_clicks()
    import faulthandler
    dump_secs = os.environ.get("MPLAYER_DUMP_SECS")
    dump_file = os.environ.get("MPLAYER_DUMP_FILE")
    if dump_secs and dump_file:
        try:
            faulthandler.dump_traceback_later(int(dump_secs),
                                              file=open(dump_file, "w"))
        except Exception:
            pass
    auto = QTimer()
    auto.setInterval(400)

    def dismiss():
        m = QApplication.activeModalWidget()
        if isinstance(m, QMessageBox):
            m.accept()

    auto.timeout.connect(dismiss)
    auto.start()
    app._auto = auto  # GC防止 (参照保持)
    return app


def _patch_key_clicks():
    """QTest.keyClick を「押す前にウィンドウを前面に出す」版に差し替える。

    この環境では前面に無いウィンドウのショートカットが無視され、キー入力が
    黙って捨てられることがある (テストがまぐれで落ちる原因)。各テストが
    個別に対応しなくて済むよう、make_app() から 1 回だけ差し替える。
    マウス操作や qWait はそのまま (元の実装に委譲する)。
    """
    from PySide6.QtTest import QTest

    if getattr(QTest.keyClick, "_mplayer_activated", False):
        return
    original = QTest.keyClick

    def keyClick(widget, *args, **kwargs):
        window = getattr(widget, "window", None)
        if callable(window):
            try:
                activate_window(window())
            except Exception:
                pass
        return original(widget, *args, **kwargs)

    keyClick._mplayer_activated = True
    keyClick._mplayer_original = original
    QTest.keyClick = keyClick


def finish(name):
    print(f"== {name} RESULT: {passed} passed, {failed} failed, {skipped} skipped ==", flush=True)
    return 1 if failed else 0


def _win_handles():
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    k32.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k32.GetProcessHandleCount.restype = wintypes.BOOL
    return k32, psapi


def rss_mb_win():
    """自プロセスのRSS(MB)をWindows APIで取得。psutil不要 (クリーン環境対応)。"""
    try:
        import ctypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]

        k32, psapi = _win_handles()
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        if psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
            return pmc.WorkingSetSize / 1024 / 1024
    except Exception:
        pass
    return -1.0


def handles_win():
    """自プロセスのハンドル数をWindows APIで取得。psutil不要。"""
    try:
        import ctypes
        from ctypes import wintypes
        k32, _ = _win_handles()
        n = wintypes.DWORD(0)
        if k32.GetProcessHandleCount(k32.GetCurrentProcess(), ctypes.byref(n)):
            return int(n.value)
    except Exception:
        pass
    return -1


def silence(w):
    """テスト中の音出しを止める (440Hzサインがうるさいため)。
    音量0にするだけでデコード自体は継続するので、PCMタップ等の検証に影響しない。"""
    try:
        w.vol.setValue(0)
    except Exception:
        pass
