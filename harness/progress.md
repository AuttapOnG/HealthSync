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
- Completed HS-008 Zepp Life source POC. After user feedback, selected a
  user-owned Zepp Life app session as the preferred live POC path, using
  captured `apptoken`, user id, and regional host for read-only weight records.
  Kept Zepp Life personal data export, Google Fit/Health Connect, and Mi
  Fitness export as fallbacks. Added `docs/zepp_life_source_poc.md`,
  `scripts/zepp_life_login_weight_poc.py`, `scripts/zepp_life_weight_poc.py`,
  and non-private sample files.
- Added `zepp-life-mcp` into the project as pinned POC/reference tooling via
  `requirements-poc.txt` and `docs/zepp_life_mcp_poc.md`. This gives a
  project-local way to test Zepp cloud session and export-file modes without
  making the HealthSync runtime depend on MCP yet.
- Live Zepp/Huami privacy-page session test reached
  `api-mifit.huami.com`. `weightRecords` returned an empty list, but
  `GET /users/{user_id}` returned a profile-level latest weight, so the
  HealthSync login POC now falls back to profile weight when records are empty.
- Created a local ignored `.env` for Zepp POC credentials and updated
  `scripts/zepp_life_login_weight_poc.py` to load `.env` automatically.
- Completed HS-002 canonical weight model. Added `healthsync.models.WeightMeasurement`
  with source, measured timestamp, weight, optional body composition fields,
  metadata, validation, and a stable duplicate-detection sync key. Added
  `tests/test_models.py` and `requirements-dev.txt` for pytest-based tests.

### Next Up

- Add source and destination interfaces.
- Add file-based source and dry-run destination.
- Add file-based sync state for duplicate prevention.

### Open Questions

- Can the user's actual Zepp Life app session provide weight data from
  `GET /users/{id}/members/-1/weightRecords` with the captured regional host,
  or does it require an account-specific endpoint variation?
- Does the user's actual Zepp Life export include `BODY/BODY_*.csv` with the
  expected weight columns, if API login/session access becomes impractical?
- Should v0.1 sync only the latest measurement or all unsynced historical records?
- Should cloud deployment use local file state, Cloud Storage, Firestore, or another state backend?
