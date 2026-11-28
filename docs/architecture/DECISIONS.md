# Architecture decisions

## ADR-001: Keep `state_paths` and `json_persistence` as narrow leaves

Status: accepted.

They are small but own real policy and pass the deletion test (removing them breaks `main`, `updater`, and tests). Merging them into `main` would make `updater` depend on PySide6. Keep `state_dir()` dynamic so `MPLAYER_STATE_DIR` changes after import remain observable.

## ADR-002: Do not split `PlayerWindow` into mixins during entropy work

Status: accepted.

Its methods share mutable state and initialization order; tests call private methods/fields directly. Splitting relocates complexity rather than removing it. Only extract pure helpers with stable call contracts.

## ADR-003: Version authority stays as the literal `__version__` in `main.py`

Status: accepted.

`mplayer.spec`, CI, installer maker, help, and release tests consume that literal. Moving it would require coordinated changes across build/test contracts with no complexity reduction.

## ADR-004: Normalize by deletion first

Status: accepted.

Before adding any shared abstraction, verify the old implementation has callers migrated and can be deleted. Prefer one authority per concept; keep compatibility only when an external contract requires it.

## ADR-005: Treat exact README/CHANGELOG prose as a hard contract for now

Status: accepted (provisional; product decision needed to change).

Many tests assert exact strings. Rewording documentation is excluded from entropy rounds until explicitly authorized.

## ADR-006: Keep updater status strings as the UI protocol

Status: accepted.

The toast branches on exact Japanese prefixes and tests assert icons/colors. Changing wording changes behavior. Normalize internals only.
