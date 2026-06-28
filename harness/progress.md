# HealthSync Progress

## 2026-06-27

### Decisions

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
- Run a Garmin Connect destination POC before implementing the full Garmin
  adapter because Garmin authentication, 2FA, and weight upload behavior need
  confirmation.

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
  Added `docs/zepp_life_source_poc.md`,
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
- Completed HS-003 adapter interfaces. Added source and destination protocols
  for weight measurements, plus a small `WeightSyncEngine` that fetches
  canonical measurements from a source and uploads them through a destination
  without provider-specific logic. Added tests using fake adapters to verify
  structural interface use, upload coordination, and failed-upload logging.
- Completed HS-010 Garmin Connect weight destination POC. Investigated
  `python-garminconnect` and `garth`; selected `python-garminconnect` for
  HS-007 because `garth` is deprecated and new logins are not a practical base.
  Added Garmin placeholders to `.env.example`, documented auth/session/2FA,
  upload fields, risks, and HS-007 plan in `docs/garmin_connect_poc.md`, and
  added `scripts/garmin_weight_poc.py` with dry-run-first mapping,
  auth-check, and explicit double-confirmation before any real upload.
- Live Garmin verification succeeded with user-provided local credentials:
  MFA login worked, reusable session tokens were saved under the ignored
  `GARMIN_SESSION_DIR`, read-only weight endpoints returned historical records,
  and a guarded `109.0 kg` upload was confirmed by read-back as one 2026-06-27
  manual entry (`109000.0` grams). HS-007 must remember that Garmin upload
  accepts kg with `unitKey="kg"`, while read-back weight values are grams.
- Completed HS-005 file-based sync state for duplicate prevention. Added
  `FileSyncState` with default local ignored path `data/sync_state.json` and
  optional `HEALTHSYNC_SYNC_STATE_PATH`, integrated optional state into
  `WeightSyncEngine`, skipped already synced weight measurements, and marked
  only successful uploads as synced. Added tests for mark synced, duplicate
  skip, failed-upload behavior, and load/save state. Verified with
  `python -m pytest` and `python -m compileall healthsync scripts`.
- Completed HS-004 Zepp Life weight source adapter. Added
  `healthsync/sources/zepp_life.py` with environment/injectable session
  configuration, read-only `weightRecords` fetching, profile latest-weight
  fallback when records are empty, canonical `WeightMeasurement` mapping, and
  clear errors for invalid responses or missing configuration. Added
  `tests/test_zepp_life_source.py` for mapping, empty records, fallback,
  invalid responses, and config validation. Documented optional `ZEPP_DAYS` in
  `.env.example`. Verified with `python -m pytest` and
  `python -m compileall healthsync scripts`.
- Completed HS-006 dry-run destination. Added `DryRunWeightDestination` under
  `healthsync/destinations/` to record canonical measurements that would be
  uploaded without credentials or external API calls. Added tests covering the
  destination interface, stored would-upload measurements, and sync engine use.
- Completed HS-007 Garmin weight destination. Added
  `healthsync/destinations/garmin.py` with environment/injectable
  configuration, token-session login first, credential fallback, canonical
  weight/body-composition mapping, and clear config/auth/upload errors. Added
  fake-client tests for Garmin mapping, configuration validation,
  authentication failure, upload failure, and failed-upload sync-state
  behavior.
- Added local runner in `scripts/sync_weight.py`. It defaults to dry-run,
  wires `ZeppLifeWeightSource` through `FileSyncState` into dry-run or Garmin,
  and refuses Garmin uploads unless `HEALTHSYNC_ALLOW_REAL_UPLOAD=true` and
  `--allow-real-upload` are both present in the runtime command.
- After the first live local end-to-end run, Garmin showed the synced `107.4 kg`
  value. Fixed two local-run polish issues discovered during that test:
  dry-run no longer persists sync state, and file sync state loading accepts
  UTF-8 BOM files produced by some Windows tooling.
- Added optional Garmin read-back verification after weight upload. The Garmin
  destination can now read weight records for the uploaded measurement date,
  convert Garmin read-back grams to kg, and raise a clear verification error
  when no matching weight is found so sync state is not marked synced. The
  behavior defaults off via `GARMIN_VERIFY_UPLOADS=false` to avoid extra real
  Garmin reads unless explicitly enabled.

### Next Up

- See the 2026-06-28 update for HS-009 cloud function work.

### Open Questions

- Zepp Life app-session access is unofficial and tokens can expire; local runs
  still depend on a valid user-owned `ZEPP_APP_TOKEN`, `ZEPP_USER_ID`, and
  regional `ZEPP_HOST`.
- Should v0.1 sync only the latest measurement or all unsynced historical records?
- Where should Garmin session tokens live in cloud deployment: Secret Manager,
  Cloud Storage, or another managed store?
- Garmin upload verification still depends on unofficial Garmin Connect read
  endpoints and may need adjustment if `python-garminconnect` changes the
  `get_weigh_ins` response shape or signature.

## 2026-06-28

### Decisions

- Use Google Cloud Storage as the first cloud duplicate-prevention state
  backend for HS-009 because it preserves the local JSON state shape and keeps
  deployment simpler than adding a database.
- Keep the Cloud Functions HTTP entrypoint safe by default: it uses dry-run
  unless `HEALTHSYNC_DESTINATION=garmin`, and Garmin uploads still require
  `HEALTHSYNC_ALLOW_REAL_UPLOAD=true`.

### Completed

- Completed HS-009 cloud function entrypoint. Added `main.sync_weight_http`,
  which reuses `ZeppLifeWeightSource`, `GarminWeightDestination` or
  `DryRunWeightDestination`, configured sync state, and `WeightSyncEngine`.
- Added `CloudStorageSyncState` for durable Google Cloud Storage-backed
  duplicate prevention, selected with `HEALTHSYNC_STATE_BACKEND=gcs`.
- Added runtime dependencies in `requirements.txt`.
- Added `docs/cloud_function.md` with local `functions-framework` execution,
  cloud environment variables, GCS state settings, and secret-handling notes.
- Updated `.env.example` and `README.md` with cloud destination/state settings.
- Added tests for the HTTP entrypoint, upload safety gate, and GCS sync state.
  Verified with `python -m pytest` and
  `python -m compileall healthsync scripts main.py`.
- Deployed `healthsync-weight-sync` to Google Cloud project
  `healthsync-84gaec` in `us-central1`, using GCS state bucket
  `healthsync-84gaec-state`, Secret Manager provider secrets, and real Garmin
  upload mode.
- Added Garmin session-token cache loading from Secret Manager and verified a
  real cloud upload succeeded; a second run skipped the same measurement via
  GCS duplicate state.
- Created Cloud Scheduler job `healthsync-weight-sync-every-4h` with cron
  `0 */4 * * *` in timezone `Asia/Bangkok`, replacing the initial every-6-hour
  schedule after confirming provider/API risk was still low. The first
  every-6-hour scheduled trigger had already invoked the function successfully
  at 2026-06-28 18:00 Asia/Bangkok.
- Created Google Cloud Billing budget `HealthSync monthly guardrail` for
  project `healthsync-84gaec` at 35 THB/month, with alerts at 50%, 90%, and
  100% current spend.

### Next Up

- Monitor the next few scheduled runs for Zepp token expiry or Garmin auth
  changes.

### Open Questions

- Zepp Life app-session access is unofficial and tokens can expire; cloud runs
  still depend on a valid user-owned `ZEPP_APP_TOKEN`, `ZEPP_USER_ID`, and
  regional `ZEPP_HOST`.
- Should v0.1 sync only the latest measurement or all unsynced historical records?
- Garmin upload verification still depends on unofficial Garmin Connect read
  endpoints and may need adjustment if `python-garminconnect` changes the
  `get_weigh_ins` response shape or signature.
