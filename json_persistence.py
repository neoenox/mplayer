"""Crash-safe JSON persistence helpers for user state files."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_json(
    path: str | os.PathLike[str],
    data: Any,
    *,
    ensure_ascii: bool = False,
    indent: int | None = None,
) -> None:
    """Write JSON via a same-directory temp file and atomic replacement.

    The destination is never opened with truncation. If serialization, flush,
    fsync, or replacement fails, the previous destination remains untouched
    and the temporary file is removed.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(
                data,
                temporary_file,
                ensure_ascii=ensure_ascii,
                indent=indent,
            )
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
