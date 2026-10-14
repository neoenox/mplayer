"""E2Eテスト共通ヘルパー (P1/P2用)。"""
import os
import sys

from PySide6.QtCore import QEventLoop, QTimer
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


def make_app():
    app = QApplication(sys.argv)
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
