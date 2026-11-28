# Architecture progress

## Baseline

- Worktree: `C:/vibe/mplayer-arch` (branch `arch-work-2`)
- Base commit: `999afc7 refactor: consolidate state paths and shared lookup/trim helpers`
- Full suite after round 2: 1436 passed / 0 failed / 1 skipped (offscreen subtitle composite). Build artifacts copied into worktree for `p8_exe`/`p15_installer`.
- Product: Windows PySide6/QtMultimedia player, PyInstaller one-folder portable + Inno Setup per-user installer, silent updater from GitHub Releases with SHA256, 45 E2E stages.

## Survey status

- [x] Module/dependency inventory
- [x] State ownership map
- [x] Duplicate implementation list
- [x] Test/build/release contract inventory
- [x] Design decisions and ranked task pool
- [x] Round 1 migration complete
- [x] Round 1 independent review
- [x] Round 1 verification recorded

See `MAP.md`, `DECISIONS.md`, `TASK_POOL.md`.

## Round 1

Goal: only behavior-preserving deletions and normalization with mechanical guards.

- [x] Delete dead `main._write_json_atomic` (duplicates `json_persistence.atomic_write_json`).
- [x] Remove dead updater symbols (`PRESERVE_FILES`, `take_pending`).
- [x] Reuse `json_persistence.atomic_write_json` for Python-side update result marker.
- [x] Single authority for supported video extensions and file-dialog filter.
- [x] Single helper for subtitle outline width.
- [x] Share audio-device enumeration helper between menu refresh and output-change handler.
- [x] Add contract checks for the normalized invariants.
- [x] Run narrow checks, full suite, and independent review. Full suite: 1420 passed / 1 flaky `p6_controls` failure; isolated rerun 5/5 PASS. `p8_exe`/`p15_installer` skipped because the worktree has no `dist/` artifacts.

## Round 2 (complete)

- [x] Consolidate `test_p0_decode.py` local `check`/`RESULT` into `tests/helpers.py`.
- [x] Derive newer-than-current version fixture in `p11_release`.
- [x] Select installer by exact version in `p15_installer`; historical-only artifacts now FAIL instead of vacuously passing.
- [x] Verify env restoration in `p11_release` (already correct; no change needed).
- [x] Register `p38_atomic_json` next to other p38 stages; rename RESULT label.
- [x] Round 2 independent review; non-blocking findings fixed.
