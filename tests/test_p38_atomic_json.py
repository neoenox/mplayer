"""P38: atomic JSON persistence preserves the last valid state on failure."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers import check, finish
import json_persistence
from json_persistence import atomic_write_json


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

    return finish("P38")


if __name__ == "__main__":
    sys.exit(main())
