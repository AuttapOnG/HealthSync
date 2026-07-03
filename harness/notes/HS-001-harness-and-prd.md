# HS-001 Create project harness and PRD

Status: done · Branch: -

## Decisions

- HealthSync should be a pluggable sync system, not a Garmin wellness data fetcher.
- The first real use case is weight sync.
- Garmin Connect is the first destination.
- Zepp Life user-owned app session is the first real source path.
- A Zepp Life source POC should happen before building too much architecture.
- File, CSV, and export-based source fallbacks are out of scope for v0.1.
- The core architecture should be source adapter -> canonical model -> destination adapter.
- Keep `AGENTS.md` at the repo root as the primary agent hook.
- Keep harness state files under `harness/` so implementation context is organized and easy to find.
- Use feature branches for implementation work.
- Commit only when the user asks or the task explicitly includes committing.

## Completed

- Created initial PRD in `docs/PRD.md`.
- Created agent harness instructions in `AGENTS.md`.
- Created implementation queue in `harness/feature_list.json`.
- Created the harness progress log (`harness/progress.md`).
- Added `harness/README.md` as the harness entrypoint.
- Initialized git repository.
- Added `.gitignore` for Python caches, virtual environments, local secrets, and local sync state.
- Added git branch and commit policy to the harness.

## Remaining risk / dead-ends

- None known.
