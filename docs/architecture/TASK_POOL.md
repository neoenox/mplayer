# Refactor task pool

Ranking = (complexity removed × safety) / churn. Status values: todo, doing, done, blocked.

| # | Task | Entropy removed | Risk | Churn | Status |
|---|---|---|---|---|---|
| 1 | Delete dead `main._write_json_atomic` | Medium | None | 1 file | done |
| 2 | Delete dead updater symbols `PRESERVE_FILES`, `take_pending` | Low | None | 1 file | done |
| 3 | Use `atomic_write_json` for update-result marker | Low | Low | 1 file | done |
| 4 | Single authority for video extensions and dialog filter | Medium | Low | 1 file + test | done |
| 5 | Single helper for subtitle outline width | Low | Low | 1 file | done |
| 6 | Share audio-device enumeration helper | Low | Medium | 1 file | done |
| 7 | Add contract checks for normalized invariants | Medium | None | tests | done |
| 8 | Consolidate `test_p0_decode` local helpers | Low | Low | tests | done |
| 9 | Derive newer-than-current version fixture instead of `v1.31.0` | Medium | Low | tests | done |
| 10 | Select installer by exact version in `p15` | Medium | Low | tests | done |
| 11 | Verify `MPLAYER_NO_AUTOUPDATE` env restoration in `p11` | Low | Low | tests | done (already correct) |
| 12 | Register `p38_atomic_json` next to other p38 stages | Low | Low | tests | done |
| 13 | Interpolate tuning constants into help prose | Medium | Medium | docs/tests | blocked: product decision |
| 14 | Generalize deferred-generation helper | Low | Medium | main | done |
| 15 | Consolidate seek commit sequence | Low | Medium | main | done |
| 16 | Extract pure subtitle text helpers | Medium | Medium | main + tests | done |
| 17 | Extract pure state validators | Medium | High | main + many tests | todo (later round) |
| 18 | Split `PlayerWindow` into mixins | Negative | High | whole app | rejected (deletion test) |
| 19 | Move `__version__` out of `main.py` | Negative | High | build/CI | rejected (deletion test) |

## Round 1 scope

Tasks 1–7 only. Each migration must update all callers, delete the old implementation, and add a mechanical guard where practical. Verification: narrow stages then full suite; independent review before commit.
