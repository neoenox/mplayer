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

## Round 3 (complete)

- [x] Extract pure subtitle text helpers into `subtitle_text.py` with re-exports from `main.py`.
- [x] Add `_defer_current_media()` and migrate generation-guarded callbacks.
- [x] Add `_commit_seek()` and migrate seek sites; keep A-B EOS on a direct slider update.
- [x] Independent review found one behavior regression at the A-B loop boundary; fixed before verification.
- [x] Add p11 authority guard and A-B EOS regression guard.
- [x] Narrow checks 355 passed / 0 failed / 1 skipped; final full suite 1437 passed / 0 failed / 1 skipped after the A-B EOS fix.

## Round 4 (converged)

- [x] Add AST guard: no leaf module imports `main`; `main` imports all leaf modules.
- [x] Dead-definition scan: no unused module-level symbols remain in runtime modules.
- [x] Review remaining tasks: metadata formatter family = low gain; help prose interpolation = product decision; state-validator extraction = mixed concepts / negative deletion-test value; `PlayerWindow` split and version move = rejected.
- [x] Final verification: full suite 1442 passed / 0 failed / 1 skipped (offscreen subtitle composite).

No further safe high-value entropy reduction remains in this round. Proceed only on new requirements or an explicit product decision about documentation wording.
