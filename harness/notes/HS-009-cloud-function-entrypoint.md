# HS-009 Add cloud function entrypoint

Status: done · Branch: -

## Decisions

- Use Google Cloud Storage as the first cloud duplicate-prevention state
  backend because it preserves the local JSON state shape and keeps
  deployment simpler than adding a database.
- Keep the Cloud Functions HTTP entrypoint safe by default: it uses dry-run
  unless `HEALTHSYNC_DESTINATION=garmin`, and Garmin uploads still require
  `HEALTHSYNC_ALLOW_REAL_UPLOAD=true`.
- The HTTP entrypoint must not leak exception details (bucket names, env var
  names) in 500 responses; details live in Cloud Logging only.
- Where should Garmin session tokens live in cloud deployment? Resolved:
  Secret Manager (see Completed below), with the local token cache file as
  an alternate local-only store.

## Completed

- Completed HS-009 cloud function entrypoint. Added `main.sync_weight_http`,
  which reuses `ZeppLifeWeightSource`, `GarminWeightDestination` or
  `DryRunWeightDestination`, configured sync state, and `WeightSyncEngine`.
- Added `CloudStorageSyncState` for durable Google Cloud Storage-backed
  duplicate prevention, selected with `HEALTHSYNC_STATE_BACKEND=gcs`. (Its
  optimistic-concurrency hardening is recorded in
  `harness/notes/HS-005-sync-state.md`.)
- Added runtime dependencies in `requirements.txt`.
- Added `docs/cloud_function.md` with local `functions-framework` execution,
  cloud environment variables, GCS state settings, and secret-handling
  notes.
- Updated `.env.example` and `README.md` with cloud destination/state
  settings.
- Added tests for the HTTP entrypoint, upload safety gate, and GCS sync
  state. Verified with `python -m pytest` and
  `python -m compileall healthsync scripts main.py`.
- `main.sync_weight_http` now returns a generic 500 error body instead of
  exception details, per the no-leak decision above
  (`healthsync/destinations/garmin.py` login-failure logging and the sync
  engine fail-fast behavior that this depends on are cross-cutting; see
  `harness/progress.md`).

## Remaining risk / dead-ends

- The deployed Cloud Function service account may need additional Secret
  Manager permissions before Garmin token persistence can work reliably in
  production (see the deployment log in `harness/progress.md`).
