"""Regression checks for invalid test-runner stage selections."""
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tests" / "run_all.py"


def verify_invalid_stage(args):
    result = subprocess.run(
        [sys.executable, str(RUNNER), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 2, (args, result.returncode, result.stderr)
    assert "unknown stage(s):" in result.stderr, result.stderr
    print(f"[PASS] rejected invalid stages: {args}")


if __name__ == "__main__":
    verify_invalid_stage(["does_not_exist"])
    verify_invalid_stage(["p6_controls", "does_not_exist"])
