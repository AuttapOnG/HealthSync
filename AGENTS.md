# HealthSync Agent Instructions

## Mission

Build HealthSync as a pluggable health metric sync system. The first working use case is body weight sync into Garmin Connect. Keep the implementation small, testable, and ready to extend.

## Product Scope

Before implementing product behavior, read the harness in this order:

1. `harness/README.md`
2. `harness/progress.md`
3. `harness/feature_list.json`
4. `docs/PRD.md`

Do not implement from memory. If these files conflict, prefer the newest decision in `harness/progress.md`, then `harness/feature_list.json`, then `docs/PRD.md`.

Current scope:

- Metric: weight only.
- Initial destination: Garmin Connect.
- Initial source: Zepp Life user-owned app session path confirmed by the POC.
- Architecture: source adapter -> canonical model -> destination adapter.

Out of scope for now:

- Sleep sync.
- Activity sync.
- Heart rate sync.
- Readiness or body battery sync.
- Dashboard UI.
- File, CSV, or export-based source fallback.
- Broad multi-metric provider support before weight sync works.

## Engineering Rules

- Keep provider API code out of the sync engine.
- Put source integrations under `healthsync/sources/`.
- Put destination integrations under `healthsync/destinations/`.
- Use canonical models from `healthsync/models.py` between adapters.
- Add or update tests for sync logic, duplicate detection, and adapter mapping.
- Make local development work before cloud deployment.
- Never commit real `.env` files, credentials, tokens, or provider cookies.

## Git Branch And Commit Policy

- Work on a feature branch for every implementation task.
- Do not commit directly to `main` unless the user explicitly asks or the change is an initial project setup milestone.
- Use branch names that describe the tracked work, such as `feature/HS-002-weight-model`, `feature/HS-004-zepp-life-source`, `fix/<short-description>`, or `docs/<short-description>`.
- Before starting work, run `git status --short` and check the current branch.
- If there are uncommitted changes, do not overwrite them. Continue only when the changes clearly belong to the current task; otherwise ask the user.
- Do not auto-commit after every edit.
- Commit only when the user asks, or when the task explicitly includes committing.
- Before committing, review `git status --short`, stage only relevant files, and run relevant checks when code exists.
- Prefer one commit per completed feature, bug fix, or documentation milestone.
- Commit messages should be concise and describe the completed outcome.

## Expected Harness Files

- `docs/PRD.md`: product direction and acceptance criteria.
- `harness/README.md`: harness entrypoint and read order.
- `harness/feature_list.json`: implementation queue and status.
- `harness/progress.md`: running log of decisions, completed work, and blockers.
- `AGENTS.md`: these instructions.

## Suggested Commands

When code exists, prefer these checks:

```powershell
python -m pytest
python -m compileall healthsync
```

If a formatter or linter is added later, update this section and use the repo's configured commands.

## Definition Of Done

A feature is done only when:

- It satisfies the acceptance criteria in `harness/feature_list.json`.
- It does not break existing tests.
- It updates `harness/progress.md` with what changed and any remaining risk.
- Any new configuration is documented in `.env.example` or README.
- The work is ready for a focused commit or already committed at the user's request.

## Adapter Design

Source adapters should expose a small method that returns canonical measurements.

Destination adapters should expose a small method that accepts canonical measurements.

The sync engine should coordinate work but should not know provider-specific fields, endpoints, or authentication flows.

## Error Handling

- External provider failures should be caught and logged clearly.
- Failed uploads must not be marked as synced.
- Missing optional metric fields should stay `None`.
- Fatal configuration errors should fail fast with a clear message.
