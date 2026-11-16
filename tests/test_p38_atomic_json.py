"""P38: atomic JSON persistence preserves the last valid state on failure."""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers import check, finish
import json_persistence
from json_persistence import atomic_write_json
import main as player_main


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mplayer-atomic-json-") as directory:
        root = Path(directory)
        target = root / "resume.json"
        previous = '{"old": true}'
        target.write_text(previous, encoding="utf-8")

        try:
            atomic_write_json(target, {"new": 1}, ensure_ascii=False, indent=2)
            loaded = json.loads(target.read_text(encoding="utf-8"))
            check("successful atomic write replaces valid JSON", loaded == {"new": 1})
        except Exception as exc:
            check("successful atomic write replaces valid JSON", False, str(exc))

        target.write_text(previous, encoding="utf-8")
        original_replace = json_persistence.os.replace

        def fail_replace(source, destination):
            raise OSError("simulated replace failure")

        try:
            json_persistence.os.replace = fail_replace
            try:
                atomic_write_json(target, {"replacement": True})
                replace_failed = False
            except OSError:
                replace_failed = True
        finally:
            json_persistence.os.replace = original_replace

        check("replace failure is reported", replace_failed)
        check(
            "replace failure preserves previous JSON",
            target.read_text(encoding="utf-8") == previous,
        )
        check(
            "replace failure removes temporary file",
            not list(root.glob(".resume.json.*.tmp")),
        )

        try:
            atomic_write_json(target, {"not_json": object()})
            serialization_failed = False
        except TypeError:
            serialization_failed = True

        check("serialization failure is reported", serialization_failed)
        check(
            "serialization failure preserves previous JSON",
            target.read_text(encoding="utf-8") == previous,
        )
        check(
            "serialization failure removes temporary file",
            not list(root.glob(".resume.json.*.tmp")),
        )


    class _Value:
        def __init__(self, value):
            self._value = value

        def value(self):
            return self._value

        def isChecked(self):
            return self._value

    class _SessionOwner:
        _resume = {}
        vol = _Value(50)
        mute_btn = _Value(False)
        _rates = [1.0]
        _rate_idx = 0
        _sub_size = 20
        _sub_pos = 80
        _sub_outline = 1
        _sub_bg = 0
        _subs_pref = True
        _sub_encoding = "UTF-8"
        _sub_color = (255, 255, 255)
        _sub_font = "Arial"
        _sub_delay_ms = 0
        _shuffle = False
        _repeat = False
        _recent = []

        def playlist_paths(self):
            return []

        def window_state_for_save(self):
            return {}

    class _CaptureHandler(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []

        def emit(self, record):
            self.records.append(record)

    logger = logging.getLogger(player_main.__name__)
    handler = _CaptureHandler()
    original_writer = player_main.atomic_write_json

    def fail_write(*args, **kwargs):
        raise OSError("simulated disk full")

    logger.addHandler(handler)
    player_main.atomic_write_json = fail_write
    try:
        owner = _SessionOwner()
        player_main.PlayerWindow._save_resume(owner)
        player_main.PlayerWindow._save_session(owner)
    finally:
        player_main.atomic_write_json = original_writer
        logger.removeHandler(handler)

    messages = [record.getMessage() for record in handler.records]
    check(
        "resume save failure is logged",
        any("Failed to save resume state" in message for message in messages),
    )
    check(
        "session save failure is logged",
        any("Failed to save session state" in message for message in messages),
    )

    return finish("P38")


if __name__ == "__main__":
    sys.exit(main())
