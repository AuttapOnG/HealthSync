# HealthSync Progress

## 2026-06-27

### Decisions

- HealthSync should be a pluggable sync system, not a Garmin wellness data fetcher.
- The first real use case is weight sync.
- Garmin Connect is the first destination.
- Zepp Life is the intended first real source, but the extraction path is still an open question.
- A Zepp Life source POC should happen before building too much architecture.
- A file-based source should remain the fallback so the architecture can be tested if Zepp Life access is not practical.
- The core architecture should be source adapter -> canonical model -> destination adapter.
- Keep `AGENTS.md` at the repo root as the primary agent hook.
- Keep harness state files under `harness/` so implementation context is organized and easy to find.
- Use feature branches for implementation work.
- Commit only when the user asks or the task explicitly includes committing.

### Completed

- Created initial PRD in `docs/PRD.md`.
- Created agent harness instructions in `AGENTS.md`.
- Created implementation queue in `harness/feature_list.json`.
- Created this progress log.
- Added `harness/README.md` as the harness entrypoint.
- Initialized git repository.
- Added `.gitignore` for Python caches, virtual environments, local secrets, and local sync state.
- Added git branch and commit policy to the harness.

### Next Up

- Run Zepp Life source POC and document the selected source path or fallback.
- Implement `WeightMeasurement`.
- Add source and destination interfaces.
- Add file-based source and dry-run destination.
- Add file-based sync state for duplicate prevention.

### Open Questions

- What exact Zepp Life data extraction path should be used?
- Should v0.1 sync only the latest measurement or all unsynced historical records?
- Should cloud deployment use local file state, Cloud Storage, Firestore, or another state backend?
