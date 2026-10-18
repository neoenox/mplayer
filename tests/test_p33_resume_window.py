"""P33: 前回再生位置の記憶範囲 (短い動画でも途中再開できるか)。

従来は先頭側 5 秒 / 終端側 10 秒の固定の余裕だったため、15 秒未満の動画は
常に「記憶対象外」になり、30 秒の動画でも 5〜20 秒しか記憶できなかった。
余裕を動画長に応じて縮めることで短い動画でも途中再開できることを確かめる。
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(BASE, "tmp_p33")
SESSION = os.path.join(TMP, "session.json")
RESUME = os.path.join(BASE, "resume.json")

os.makedirs(TMP, exist_ok=True)
os.environ["MPLAYER_SESSION_FILE"] = SESSION
if os.path.isfile(RESUME):
    os.remove(RESUME)

from helpers import (check, finish, make_app,  # noqa: E402
                     patch_message_boxes, silence, wait_until)

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtMultimedia import QMediaPlayer  # noqa: E402

from main import (RESUME_MIN_MS, RESUME_TAIL_MS,  # noqa: E402
                  PlayerWindow, resume_head_ms, resume_pos_saveable,
                  resume_tail_ms)

SRC = os.path.join(BASE, "test_640x360.mp4")
CLIP = os.path.join(TMP, "clip.mp4")
CLIP_ABS = os.path.abspath(CLIP)


def pump(ms=0):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def resume_file():
    try:
        with open(RESUME, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def pause_and_remember(w):
    """(再生中にしてから) 一時停止し、位置を記憶させる。"""
    if w.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
        w.player.play()
        wait_until(lambda: w.player.playbackState() ==
                   QMediaPlayer.PlaybackState.PlayingState, 3000)
    w.toggle_play()
    wait_until(lambda: w.player.playbackState() !=
               QMediaPlayer.PlaybackState.PlayingState, 3000)
    pump(250)


def main():
    patch_message_boxes()
    make_app()
    shutil.copyfile(SRC, CLIP)

    # --- 先頭側の余裕 (純粋関数) ---
    check("60 秒の動画は既定値のまま", resume_head_ms(60000) == RESUME_MIN_MS,
          str(resume_head_ms(60000)))
    check("50 秒でも既定値", resume_head_ms(50000) == RESUME_MIN_MS,
          str(resume_head_ms(50000)))
    check("20 秒では 1/10 に縮む", resume_head_ms(20000) == 2000,
          str(resume_head_ms(20000)))
    check("12 秒では 1.2 秒", resume_head_ms(12000) == 1200,
          str(resume_head_ms(12000)))
    check("5 秒では 0.5 秒", resume_head_ms(5000) == 500,
          str(resume_head_ms(5000)))
    check("長さ不明 (0) は既定値", resume_head_ms(0) == RESUME_MIN_MS,
          str(resume_head_ms(0)))
    check("負の長さも既定値", resume_head_ms(-1) == RESUME_MIN_MS,
          str(resume_head_ms(-1)))

    # --- 終端側の余裕 (純粋関数) ---
    check("60 秒の動画は既定値のまま", resume_tail_ms(60000) == RESUME_TAIL_MS,
          str(resume_tail_ms(60000)))
    check("50 秒でも既定値", resume_tail_ms(50000) == RESUME_TAIL_MS,
          str(resume_tail_ms(50000)))
    check("20 秒では 1/5 に縮む", resume_tail_ms(20000) == 4000,
          str(resume_tail_ms(20000)))
    check("5 秒では 1 秒", resume_tail_ms(5000) == 1000,
          str(resume_tail_ms(5000)))
    check("長さ不明 (0) は既定値", resume_tail_ms(0) == RESUME_TAIL_MS,
          str(resume_tail_ms(0)))

    # --- 記憶してよい位置か (長い動画は従来どおり) ---
    check("60 秒の 30 秒は記憶する", resume_pos_saveable(30000, 60000) is True)
    check("60 秒の 3 秒は記憶しない", resume_pos_saveable(3000, 60000) is False)
    check("60 秒の 55 秒は記憶しない", resume_pos_saveable(55000, 60000) is False)

    # --- 記憶してよい位置か (短い動画 = 今回の修正) ---
    check("5 秒の 2 秒は記憶する", resume_pos_saveable(2000, 5000) is True)
    check("5 秒の 0.3 秒は記憶しない", resume_pos_saveable(300, 5000) is False)
    check("5 秒の 4.6 秒は記憶しない", resume_pos_saveable(4600, 5000) is False)
    check("先頭側の境界 (500ms) は記憶しない",
          resume_pos_saveable(500, 5000) is False)
    check("境界の直後 (1000ms) は記憶する",
          resume_pos_saveable(1000, 5000) is True)
    check("終端側の境界 (4000ms) は記憶しない",
          resume_pos_saveable(4000, 5000) is False)
    check("境界の直前 (3999ms) は記憶する",
          resume_pos_saveable(3999, 5000) is True)
    check("20 秒の 10 秒は記憶する", resume_pos_saveable(10000, 20000) is True)
    check("20 秒の 1.5 秒は記憶しない", resume_pos_saveable(1500, 20000) is False)
    check("20 秒の 17 秒は記憶しない", resume_pos_saveable(17000, 20000) is False)
    check("位置 0 は記憶しない", resume_pos_saveable(0, 60000) is False)
    check("長さ 0 は記憶しない", resume_pos_saveable(1000, 0) is False)
    check("負の長さは記憶しない", resume_pos_saveable(1000, -1) is False)

    # --- 実際の 5 秒動画で保存できる ---
    w = PlayerWindow()
    w.show()
    silence(w)
    w._resume = {}
    check("動画を開く", w.load(CLIP))
    check("長さを取得", wait_until(lambda: w.player.duration() > 0, 5000),
          str(w.player.duration()))
    dur = w.player.duration()
    check("約 5 秒の動画", 4500 <= dur <= 5500, str(dur))

    w.player.setPosition(2000)
    check("中央へ移動", wait_until(lambda: abs(w.player.position() - 2000) < 500, 3000),
          str(w.player.position()))
    pause_and_remember(w)
    saved = resume_file()
    got = saved.get(CLIP_ABS, {}).get("pos")
    check("短い動画でも位置が保存される", isinstance(got, int), str(saved))
    check("保存位置は中央付近", got is not None and abs(got - 2000) < 800,
          str(got))

    # --- 起動し直し相当: 別の窓で開くと復元する ---
    w2 = PlayerWindow()
    w2.show()
    silence(w2)
    check("別窓は記憶を読み込む", w2._resume_pos_for(CLIP_ABS) is not None,
          str(w2._resume))
    check("別窓で開く", w2.load(CLIP))
    check("長さを取得", wait_until(lambda: w2.player.duration() > 0, 5000))
    w2.player.pause()
    pump(400)
    pos2 = w2.player.position()
    check("短い動画でも途中から再開する", pos2 > 1500, str(pos2))
    check("再開位置が保存値に近い", got is not None and abs(pos2 - got) < 900,
          f"{pos2} vs {got}")

    # --- 先頭付近は短い動画でも記憶しない ---
    w._resume = {}
    w._save_resume()
    w.player.setPosition(200)
    pump(400)
    check("先頭付近へ移動", w.player.position() < 480, str(w.player.position()))
    w._remember_current()
    check("先頭付近は保存されない", w._resume_pos_for(CLIP_ABS) is None,
          str(w._resume))
    check("resume.json にも入らない", CLIP_ABS not in resume_file(),
          str(resume_file()))

    # --- 終端付近は短い動画でも記憶しない ---
    w.player.setPosition(4600)
    pump(400)
    check("終端付近へ移動", w.player.position() > 4000, str(w.player.position()))
    w._remember_current()
    check("終端付近は保存されない", w._resume_pos_for(CLIP_ABS) is None,
          str(w._resume))

    # --- 復元側も同じ判定 (終端付近の記憶は復元しない) ---
    w3 = PlayerWindow()
    w3.show()
    silence(w3)
    check("別窓で開く", w3.load(CLIP))
    check("長さを取得", wait_until(lambda: w3.player.duration() > 0, 5000))
    w3.player.pause()
    w3.player.setPosition(1000)
    pump(400)
    w3._restore_pos = 4600
    w3.on_duration_changed(w3.player.duration())
    pump(500)
    check("終端付近は復元しない", abs(w3.player.position() - 1000) < 600,
          str(w3.player.position()))
    w3._restore_pos = 300
    w3.on_duration_changed(w3.player.duration())
    pump(500)
    check("先頭付近も復元しない", abs(w3.player.position() - 1000) < 600,
          str(w3.player.position()))
    w3._restore_pos = 2000
    w3.on_duration_changed(w3.player.duration())
    check("中央は復元する", wait_until(
        lambda: abs(w3.player.position() - 2000) < 500, 3000),
        str(w3.player.position()))

    # --- 明示停止で忘れる (短い動画でも) ---
    w.player.setPosition(2200)
    pump(400)
    w._remember_current()
    check("記憶されている", w._resume_pos_for(CLIP_ABS) is not None,
          str(w._resume))
    w.stop()
    pump(700)
    check("停止で記憶が消える", w._resume_pos_for(CLIP_ABS) is None,
          str(w._resume))
    check("resume.json からも消える", CLIP_ABS not in resume_file(),
          str(resume_file()))
    check("停止で先頭に戻る", w.player.position() < 800, str(w.player.position()))

    # --- 後始末 ---
    for win in (w, w2, w3):
        try:
            win.close()
        except Exception:
            pass
    if os.path.isfile(RESUME):
        os.remove(RESUME)
    shutil.rmtree(TMP, ignore_errors=True)
    return finish("P33resumewindow")


if __name__ == "__main__":
    sys.exit(main())
