"""P0: 映像・音声の実デコード検証.

QVideoWidget.videoSink().videoFrameChanged で有効 QVideoFrame を監視し、
QMediaPlayer.setAudioBufferOutput(QAudioBufferOutput) でデコード済みPCMを取得する。
通常の映像表示・音声再生はそのまま (タップ追加のみ) で行い、破壊しないことを確認する。
無音動画を陰性対照にする。hasVideo/PlayingだけではPASSにしない。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtMultimedia import QAudioBufferOutput, QMediaPlayer, QVideoFrame
from PySide6.QtWidgets import QApplication, QMessageBox

from tests.helpers import patch_message_boxes, silence  # noqa: E402

from main import PlayerWindow

BASE = os.path.dirname(os.path.abspath(__file__))
VIDEO = os.path.join(BASE, "..", "test_640x360.mp4")
SILENT = os.path.join(BASE, "..", "test_silent.mp4")

passed = failed = 0


def check(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"[PASS] {name} {extra}", flush=True)
    else:
        failed += 1
        print(f"[FAIL] {name} {extra}", flush=True)


def wait_for(pred, timeout_ms=10000, poll_ms=100):
    """固定sleepではなく条件成立まで待つ。成立True/タイムアウトFalse。"""
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(poll_ms)
    state = {"done": False}

    def on_poll():
        if pred():
            state["done"] = True
            loop.quit()

    timer.timeout.connect(on_poll)
    timer.start()
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    timer.stop()
    return state["done"]


def frame_sample(frame):
    """有効フレームから (w,h,先頭バイトchecksum) を取り出す。失敗時はNone。"""
    try:
        if not frame.isValid():
            return None
        w, h = frame.width(), frame.height()
        if w <= 0 or h <= 0:
            return None
        if not frame.map(QVideoFrame.MapMode.ReadOnly):
            return (w, h, "unmappable")
        try:
            n = min(4096, frame.mappedBytes(0))
            mv = frame.bits(0)
            data = bytes(mv[:n]) if n > 0 else b""
            return (w, h, sum(data) % 1000003, len(data))
        finally:
            frame.unmap()
    except Exception as e:  # 例外でテスト全体を落とさない
        return ("exc", str(e))


def audio_sample(buf):
    """QAudioBufferから (sampleCount, 非ゼロ有無) を取り出す。"""
    try:
        if not buf.isValid():
            return (0, False)
        sc = buf.sampleCount()
        try:
            raw = bytes(buf.constData())[:8192]
        except Exception:
            try:
                raw = bytes(buf.data())[:8192]
            except Exception:
                return (sc, "unreadable")
        return (sc, any(b != 0 for b in raw), len(raw))
    except Exception as e:
        return ("exc", str(e))


def main():
    patch_message_boxes()
    app = QApplication(sys.argv)

    # 安全弁: 万一モーダルダイアログが出てもハングしないよう自動OK
    auto = QTimer()
    auto.setInterval(500)

    def dismiss():
        w = QApplication.activeModalWidget()
        if isinstance(w, QMessageBox):
            w.accept()

    auto.timeout.connect(dismiss)
    auto.start()

    w = PlayerWindow()
    frames = []   # (w,h,checksum,n)
    audios = []   # (samples, nonzero, nbytes)

    sink = w.video.videoSink()

    def on_frame(f):
        s = frame_sample(f)
        if s is not None:
            frames.append(s)
    sink.videoFrameChanged.connect(on_frame)

    buf_out = QAudioBufferOutput()
    w.player.setAudioBufferOutput(buf_out)
    audio_formats = []

    def on_audio(b):
        audios.append(audio_sample(b))
        try:
            audio_formats.append(b.format())
        except Exception:
            pass
    buf_out.audioBufferReceived.connect(on_audio)

    w.show()
    silence(w)  # 音量0 (検証中は無音。デコード自体は継続)
    vol_before = w.audio.volume()

    # --- 1. 有音動画ロード ---
    check("asset video exists", os.path.isfile(VIDEO), VIDEO)
    check("asset silent exists", os.path.isfile(SILENT), SILENT)
    ok = w.load(os.path.abspath(VIDEO))
    check("load returns True", ok)
    check("duration sane", wait_for(lambda: w.player.duration() > 4000, 10000),
          f"duration={w.player.duration()}")

    # --- 2. 映像フレーム ---
    got = wait_for(lambda: len(frames) >= 10, 15000)
    check(">=10 video frames received", got, f"n={len(frames)}")
    valid = [f for f in frames if isinstance(f, tuple) and len(f) == 4 and isinstance(f[0], int)]
    check("frames are valid w/h", len(valid) >= 10,
          f"valid={len(valid)} sample={valid[0] if valid else frames[:2]}")
    sizes = {(f[0], f[1]) for f in valid}
    check("frame resolution 640x360", sizes == {(640, 360)}, f"sizes={sizes}")
    n0 = len(frames)
    wait_for(lambda: len(frames) >= n0 + 10, 5000)
    check("frames keep updating during playback", len(frames) >= n0 + 10,
          f"before={n0} after={len(frames)}")
    checksums = {f[2] for f in valid[:30] if len(f) == 4}
    check("frame pixels vary over time (real decode)", len(checksums) > 1,
          f"distinct={len(checksums)}")

    # --- 3. 音声PCM ---
    got_a = wait_for(lambda: len(audios) >= 5, 15000)
    check(">=5 audio buffers received", got_a, f"n={len(audios)}")
    total_samples = sum(a[0] for a in audios if isinstance(a, tuple) and isinstance(a[0], int))
    check("total PCM samples > 0", total_samples > 0, f"samples={total_samples}")
    nonzero = any(a[1] is True for a in audios if isinstance(a, tuple))
    check("PCM contains non-zero signal (440Hz)", nonzero,
          f"bufs={audios[:3]}")
    fmt_ok, fmt_info = False, "no buffers"
    for fm in audio_formats:
        try:
            if fm.isValid() and fm.sampleRate() > 0 and fm.channelCount() > 0:
                fmt_ok, fmt_info = True, f"{fm.sampleRate()}Hz ch={fm.channelCount()}"
                break
            fmt_info = f"valid={fm.isValid()} sr={fm.sampleRate()} ch={fm.channelCount()}"
        except Exception as e:
            fmt_info = str(e)
    check("audio format valid", fmt_ok, fmt_info)

    # --- 4. 通常再生を壊していない ---
    check("still Playing", w.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
    check("video widget visible & sized", w.video.isVisible() and w.video.size().width() > 100,
          f"size={w.video.size().width()}x{w.video.size().height()}")
    check("volume unchanged by tap", abs(w.audio.volume() - vol_before) < 1e-6,
          f"vol={w.audio.volume()}")
    check("audio not muted by tap", not w.audio.isMuted())

    # --- 5. 陰性対照: 無音動画 ---
    frames.clear()
    audios.clear()
    w.load(os.path.abspath(SILENT))
    check("silent: hasVideo", wait_for(lambda: w.player.hasVideo(), 8000))
    got_f = wait_for(lambda: len(frames) >= 5, 12000)
    check("silent: video frames arrive", got_f, f"n={len(frames)}")
    # 切替直後に前動画の残留バッファが1個流れることがあるため、一度捨ててから観測
    loop = QEventLoop()
    QTimer.singleShot(1000, loop.quit)
    loop.exec()
    audios.clear()
    loop2 = QEventLoop()
    QTimer.singleShot(3000, loop2.quit)
    loop2.exec()
    check("silent: no audio buffers (negative control)", len(audios) == 0,
          f"n={len(audios)}")

    print(f"\n== P0 RESULT: {passed} passed, {failed} failed ==", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
