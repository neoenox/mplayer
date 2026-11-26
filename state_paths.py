"""State file locations shared by the app and the silent updater."""
from __future__ import annotations

import os


def state_dir() -> str:
    """User-writable directory for resume/session/update-result files."""
    override = os.environ.get("MPLAYER_STATE_DIR")
    if override:
        return override
    return os.path.join(
        os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "mplayer"
    )
