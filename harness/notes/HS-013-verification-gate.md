# HS-013 Verification gate (ruff, mypy, CI)

Status: in-progress · Branch: docs/harness-advancement

This feature spans three tasks in the current batch: ruff lint/format (this
task), mypy type checking (next task), and a CI workflow (final task). It is
marked `done` only once all three land.

## Decisions

- `pyproject.toml` holds all verification-gate config (`[tool.ruff]` now,
  `[tool.mypy]` added in the mypy task) so Task 3 and Task 4 extend one file
  instead of introducing separate config files.
- Ruff rule selection is `E, F, I, UP, B` at line-length 90, target
  `py312` (repo runs on Python 3.14, but py312 is the floor for syntax
  compatibility checks).
- Behavior-preservation constraint: auto-fixes and formatting must not change
  any string literal, number formatting, JSON key ordering, or logic used in
  `WeightMeasurement.sync_key` (`healthsync/models.py`) or the Garmin upload
  payload/timestamp code (`healthsync/destinations/garmin.py`). Verified by
  diffing every touched file and re-running the full test suite after fixes.

## Completed (Task 2: ruff lint + format gate)

- Installed `ruff` (already present, pinned `ruff>=0.6,<1` in
  `requirements-dev.txt`).
- Added `pyproject.toml` `[tool.ruff]` / `[tool.ruff.lint]` /
  `[tool.ruff.lint.isort]` config exactly as specified.
- Ran `ruff check --fix .` and `ruff format .`; this only reordered/merged
  imports, swapped `timezone.utc` for the `UTC` alias, dropped an unused
  import, replaced a dynamic `getattr(obj, "path")` with `obj.path`, and
  reflowed line breaks/blank lines. No string literal, f-string content, or
  JSON payload/key ordering changed.
- Manually resolved the remaining 13 lint findings that `--fix`/`format`
  could not auto-resolve (long error/help/log strings, and `sys.path.insert`
  followed by imports in `scripts/garmin_weight_poc.py` and
  `scripts/sync_weight.py`): split long string literals using adjacent
  string-literal concatenation (verified byte-identical via `eval` against
  the original source), and added `# noqa: E402` to the intentional
  path-shim imports rather than restructuring the scripts.
- Confirmed `ruff check .` and `ruff format --check .` both pass cleanly.
- Confirmed `python -m pytest -q` still reports `89 passed`.
- Updated `AGENTS.md` Suggested Commands to include `ruff check .` and
  `ruff format --check .`; removed the stale "if a linter is added later"
  TODO line.

## Remaining risk / dead-ends

- mypy is not yet configured (Task 3) and CI does not yet run these checks
  automatically (Task 4); until then this gate only runs when a developer
  invokes it manually.
