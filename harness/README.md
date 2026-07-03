# HealthSync Harness

Agents must read this folder before changing product behavior, code, tests, or project documentation.

## Environment Bootstrap

Run `bash init.sh` from the repo root to create/update the `.venv` and
install `requirements.txt`, `requirements-dev.txt`, and
`requirements-poc.txt`. It is idempotent and never prints or commits
secrets. See `README.md`'s Setup section and `harness/notes/HS-014-init-sh.md`.

## Required Read Order

1. `../AGENTS.md`
2. `progress.md`
3. `feature_list.json`
4. `../docs/PRD.md`

Do not implement from memory. If files conflict, prefer the newest decision in `progress.md`, then `feature_list.json`, then `../docs/PRD.md`.

## Files

- `progress.md`: Current State, Feature index, and the cross-cutting decisions/events log. It no longer holds per-feature day-by-day detail.
- `notes/HS-XXX-<slug>.md`: per-feature decisions, completed work, and remaining risk. One file per feature in `feature_list.json`.
- `feature_list.json`: implementation queue, status, priority, and acceptance criteria.

## Update Rules

- Record feature work in that feature's `harness/notes/HS-XXX-*.md`, not in `progress.md`.
- Put only cross-feature decisions, deployments, and project-wide policy (e.g. timezone normalization, circuit-breaker suspension, secret/credential policy) in `progress.md`'s Cross-cutting decisions & events section.
- Update the Current State paragraph and Feature index in `progress.md` whenever a feature's status changes.
- Update `feature_list.json` when a feature changes status.
- Keep acceptance criteria concrete enough for another agent to verify.

## Git Workflow

- Keep `AGENTS.md` at the repo root as the primary instruction hook.
- Use a feature branch for implementation work.
- Do not work directly on `main` except for initial setup, harness-only maintenance, or when the user explicitly asks.
- Suggested branch names include `feature/HS-002-weight-model`, `feature/HS-004-zepp-life-source`, `feature/HS-009-cloud-function-entrypoint`, `fix/<short-description>`, and `docs/<short-description>`.
- Do not auto-commit after every edit.
- Commit only when the user asks, or when the task explicitly includes committing.
- Before committing, check `git status --short`, stage only relevant files, and run relevant checks when code exists.
