# HealthSync Harness

Agents must read this folder before changing product behavior, code, tests, or project documentation.

## Required Read Order

1. `../AGENTS.md`
2. `progress.md`
3. `feature_list.json`
4. `../docs/PRD.md`

Do not implement from memory. If files conflict, prefer the newest decision in `progress.md`, then `feature_list.json`, then `../docs/PRD.md`.

## Files

- `progress.md`: running decisions, completed work, blockers, and next steps.
- `feature_list.json`: implementation queue, status, priority, and acceptance criteria.

## Update Rules

- Update `progress.md` whenever a meaningful implementation decision or blocker appears.
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
