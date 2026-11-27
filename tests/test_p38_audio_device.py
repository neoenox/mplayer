"""P38: 音声出力先を切り替えて記憶する。

- 「再生」→「音声出力先」から OS 既定 / 各デバイスを選べる
- 選択したデバイスは session.json に保存され、次回起動時に復元される
- 消えたデバイスや壊れた保存値はシステム既定へフォールバックする
"""
import json
import os
import shutil
import sys
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(BASE, "tmp_p38")
SESSION = os.path.join(TMP, "session.json")

os.makedirs(TMP, exist_ok=True)
if os.path.isfile(SESSION):
    os.remove(SESSION)
os.environ["MPLAYER_SESSION_FILE"] = SESSION

from helpers import check, finish, make_app, patch_message_boxes, silence  # noqa: E402

from PySide6.QtMultimedia import QAudioDevice, QMediaDevices  # noqa: E402
from PySide6.QtGui import QAction

from main import HELP_NOTES, PlayerWindow, audio_device_key  # noqa: E402


def read_session():
    with open(SESSION, encoding="utf-8") as f:
        return json.load(f)


def write_session(data):
    with open(SESSION, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def main():
    patch_message_boxes()
    make_app()

    devices = [d for d in QMediaDevices.audioOutputs() if not d.isNull()]
    if not devices:
        from helpers import skip
        skip("audio outputs available", "no output device in this environment")
        return finish("P38audio_device")

    w = PlayerWindow()
    w.show()
    silence(w)
    key = audio_device_key(devices[0])
    label = devices[0].description()

    check("menu exists", w._audio_device_menu is not None)
    check("default is system default", w._audio_device_key == "")
    check("menu lists all devices",
          len(w._audio_device_menu.actions()) == len(devices) + 1,
          f"actions={len(w._audio_device_menu.actions())} devices={len(devices)}")
    check("system default action checked",
          next(a for a in w._audio_device_menu.actions()
               if a.data() == "").isChecked())
    check("null device key is empty", audio_device_key(QAudioDevice()) == "")
    before_actions = len(w.findChildren(QAction))
    for _ in range(3):
        w._refresh_audio_device_menu()
    check("menu refresh does not leak actions",
          len(w.findChildren(QAction)) == before_actions,
          f"{before_actions} -> {len(w.findChildren(QAction))}")

    # メニュー操作で切り替わる (API 直接呼び出しだけではなく UI 配線も確認)。
    act = next(a for a in w._audio_device_menu.actions() if a.data() == key)
    act.trigger()
    check("device applied", audio_device_key(w.audio.device()) == key,
          f"got={audio_device_key(w.audio.device())}")
    check("menu shows chosen device", label in w._audio_device_menu.title(),
          f"title={w._audio_device_menu.title()!r}")
    check("chosen action checked",
          next(a for a in w._audio_device_menu.actions()
               if a.data() == key).isChecked())
    check("help explains device menu", any("音声出力先" in n for n in HELP_NOTES))

    w._save_session()
    check("session stores device", read_session().get("audio_device") == key,
          str(read_session().get("audio_device")))
    w.close()

    # 再起動後に復元される。
    w2 = PlayerWindow()
    w2.restore_session()
    check("device restored from session", w2._audio_device_key == key)
    check("device applied on startup", audio_device_key(w2.audio.device()) == key)
    check("restored action checked",
          next(a for a in w2._audio_device_menu.actions()
               if a.data() == key).isChecked())
    # 選択中のデバイスが抜かれた場合も既定へ戻る (hotplug 経路)。
    w2.set_audio_device(key)
    with mock.patch.object(QMediaDevices, "audioOutputs", staticmethod(lambda: [])):
        w2._on_audio_outputs_changed()
    check("removed device resets to default", w2._audio_device_key == "")
    check("removed device falls back to system default",
          audio_device_key(w2.audio.device())
          == audio_device_key(QMediaDevices.defaultAudioOutput()),
          f"got={audio_device_key(w2.audio.device())}")
    check("menu back to default only", len(w2._audio_device_menu.actions()) == 1)

    # OS の既定出力が変わると audioOutputsChanged が飛ぶ (Qt の仕様)。
    # 既定選択中は追従し、固定選択は維持する (issue #62)。
    w2.set_audio_device("")
    other = next(
        (d for d in devices
         if audio_device_key(d) != audio_device_key(QMediaDevices.defaultAudioOutput())),
        None)
    if other is not None:
        with mock.patch.object(QMediaDevices, "defaultAudioOutput",
                               staticmethod(lambda: other)):
            w2._on_audio_outputs_changed()
            check("default selection follows OS default change",
                  audio_device_key(w2.audio.device()) == audio_device_key(other),
                  f"got={audio_device_key(w2.audio.device())}")
            w2.set_audio_device(key)
            w2._on_audio_outputs_changed()
        check("fixed selection ignores OS default change",
              audio_device_key(w2.audio.device()) == key,
              f"got={audio_device_key(w2.audio.device())}")
    w2.set_audio_device("")

    # 未知の ID / 不正な型は既定へ戻す。
    w2.set_audio_device("00" * 32)
    check("unknown id falls back", w2._audio_device_key == "")
    check("fallback uses system default",
          audio_device_key(w2.audio.device())
          == audio_device_key(QMediaDevices.defaultAudioOutput()))
    w2.set_audio_device(123)
    check("non-string falls back", w2._audio_device_key == "")

    # 保存値が壊れていても起動は続く。
    write_session({"audio_device": 123})
    w3 = PlayerWindow()
    w3.restore_session()
    check("broken session ignored", w3._audio_device_key == "")
    w3._on_audio_outputs_changed()  # デバイス抜挿イベントでも落ちない
    check("menu still usable", len(w3._audio_device_menu.actions()) == len(devices) + 1)
    w3.close()

    return finish("P38audio_device")


if __name__ == "__main__":
    sys.exit(main())
