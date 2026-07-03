# HS-014 Reproducible env bootstrap (init.sh)

Status: done · Branch: docs/harness-advancement

## Decisions

- `init.sh` follows the exact contents specified in the task brief: creates
  `.venv` only if missing (idempotent), activates it, upgrades pip, installs
  `requirements.txt`, `requirements-dev.txt`, and `requirements-poc.txt` in
  that order, and prints a 3-step "next steps" block. It never echoes or
  writes any secret/credential value — the only file it references is
  `.env.example` (a template, not a real `.env`).
- `set -euo pipefail` ensures any install failure stops the script instead of
  silently continuing.
- Made executable via `chmod +x init.sh`.

## Completed

- Deleted any pre-existing `.venv` and ran `bash init.sh` on a clean checkout:
  it created `.venv`, installed all three requirements files, and exited 0
  with the expected "Done. Next steps" banner.
- In this environment, network access was available, so
  `requirements-poc.txt`'s git dependency
  (`git+https://github.com/kubulashvili/zepp-life-mcp.git@...`) resolved and
  installed successfully alongside `garminconnect`. **Known limitation to
  flag for network-restricted environments**: if that git-based POC
  dependency cannot be reached, `pip install -r requirements-poc.txt` will
  fail while `requirements.txt` and `requirements-dev.txt` still install
  cleanly. Per the task brief, that partial failure is acceptable and not a
  blocker for this feature, since the POC dependency is exploratory tooling
  (see HS-008/HS-010 notes), not required for runtime, dev tooling, or the
  test suite.
- Verified tests via the venv: `.venv/bin/python -m pytest -q` → `89 passed`.
- Re-ran `bash init.sh` a second time to confirm idempotency: no errors, all
  packages reported "Requirement already satisfied", `.venv` reused, exit 0.
- Confirmed `.venv/` does not appear in `git status --short` (`.venv/` and
  `venv/` were already present in `.gitignore` from earlier work; no change
  needed).
- **Incidental gate fix required to keep mypy green**: a fresh install
  resolved `google-cloud-storage==3.12.0` (satisfies the existing
  `google-cloud-storage>=2,<4` pin in `requirements.txt`). With this version,
  mypy reported `Module "google.cloud" has no attribute "storage"
  [attr-defined]` at `healthsync/state.py:389` for
  `from google.cloud import storage` — a known mypy limitation with
  `google.cloud`'s implicit namespace package when multiple
  `google-cloud-*` distributions (here, `google-cloud-storage` and
  `google-cloud-secret-manager`) extend the same namespace. Changed the
  import to `import google.cloud.storage as storage` (same runtime binding,
  same `storage` name used at every call site), which mypy resolves
  correctly. Re-ran `mypy healthsync` → `Success: no issues found in 11
  source files`, `ruff check .` → all checks passed, `ruff format --check .`
  → 24 files already formatted, `python -m pytest -q` → `89 passed`. No
  string literal, JSON payload, or Garmin/sync-key behavior changed.
- Documented `init.sh` as the setup entrypoint in `README.md` (new "Setup"
  section ahead of the existing manual pip-install instructions, which are
  kept for reference) and added a short "Environment Bootstrap" section to
  `harness/README.md` referencing it.
- Added HS-014 to `harness/feature_list.json` with status `done`.

## Remaining risk / dead-ends

- `requirements-poc.txt`'s git dependency pin is a bare commit SHA on a
  third-party GitHub repo; if that repo is deleted, rebased, or made
  private, `init.sh` will fail at the poc-install step even with network
  access. This is a pre-existing risk from HS-008/HS-010, not introduced by
  this task.
- The `google.cloud.storage` import-style fix is scoped to the one call site
  needed for the mypy gate to pass; if other modules later import
  `google.cloud.secret_manager` or similar in the `from google.cloud import
  X` style, watch for the same mypy namespace-package issue and apply the
  same `import google.cloud.X as X` pattern.
