# HS-013 Verification gate (ruff, mypy, CI)

Status: done · Branch: docs/harness-advancement

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

## Completed (Task 3: mypy type-check gate)

- Added `pyproject.toml` `[tool.mypy]` config: `python_version = "3.12"`
  (matching the ruff `target-version` floor), `warn_unused_ignores = true`,
  `warn_redundant_casts = true`, `disallow_untyped_defs = true`, and
  `ignore_missing_imports = true`.
- `disallow_untyped_defs = true` was chosen over full strict mode: it forces
  every function/method to carry type annotations (the highest-value check
  for a small codebase with no prior typing discipline) without requiring an
  immediate, invasive pass to satisfy `strict`'s stricter checks (e.g.
  `disallow_any_generics`, `warn_return_any`, `no_implicit_optional`), which
  would have meant touching far more call sites than this task's
  behavior-preservation scope allows.
- `ignore_missing_imports = true` was chosen because third-party dependencies
  used here (Garmin/session libraries pulled in via `requirements.txt`/
  `requirements-poc.txt`) do not ship type stubs and pulling in
  `types-*` stub packages or per-module overrides for each one was judged
  not worth the effort for a v0.1 gate; this can be tightened later on a
  per-module basis if stubs become available.
- `mypy>=1.10,<2` was already pinned in `requirements-dev.txt` (Task 1).
- Confirmed `mypy healthsync` passes with `Success: no issues found in 11
  source files`, and `python -m pytest -q` still reports `89 passed`.

## Completed (Task 4: GitHub Actions CI)

- Added `.github/workflows/ci.yml`: on every `push` and `pull_request`, runs
  on `ubuntu-latest` with Python 3.12, installs
  `requirements.txt` + `requirements-dev.txt`, then runs `ruff check .`,
  `ruff format --check .`, `mypy healthsync`, `python -m compileall
  healthsync`, and `python -m pytest -q` in sequence.
- `requirements-poc.txt` is deliberately excluded from the CI install step.
  It pulls in a git-based dependency (the Garmin POC exploration
  dependency) that is slow and occasionally unstable to resolve, and none of
  it is needed to run ruff, mypy, compileall, or the pytest suite that this
  gate checks — the POC script itself is exercised manually, not by CI.
- Validated the workflow YAML parses locally via
  `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
  (`ok`), since no local Actions runner is available in this environment.
- Re-ran all five gate commands locally as a stand-in for the CI job; all
  passed: `ruff check .` (all checks passed), `ruff format --check .` (24
  files already formatted), `mypy healthsync` (success, 11 source files),
  `python -m compileall healthsync` (all files compiled), `python -m pytest
  -q` (89 passed).

## Remaining risk / dead-ends

- The workflow has not been executed on an actual GitHub Actions runner in
  this environment (no CI access here); correctness was verified by running
  each workflow command locally in the same order and confirming the YAML
  parses. First real run on GitHub should be watched for environment-only
  discrepancies (e.g. pip resolver differences, ubuntu-latest Python 3.12
  toolchain quirks).
- `ignore_missing_imports = true` is a broad escape hatch; if third-party
  stubs become available it would be worth switching to per-module
  `[[tool.mypy.overrides]]` instead of a blanket setting.
