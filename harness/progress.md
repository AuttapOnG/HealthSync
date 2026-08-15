# HealthSync Progress

## Current State

The Cloud Function `healthsync-weight-sync` is deployed in `us-central1`
(project `healthsync-84gaec`) at revision
`healthsync-weight-sync-00010-zih`, with Garmin token Secret Manager retention
from HS-011 live. The Cloud Scheduler job
(`healthsync-weight-sync-every-4h`, cron `0 */4 * * *`, `Asia/Bangkok`) remains
enabled, GCS holds sync state, and the function service account has version
management permission only on `garmin-tokens-json`. The deployment preserved
the existing function configuration. A user-approved manual run verified the
new revision with HTTP 200, a successful duplicate-only Garmin keepalive, and
no destination suspension. Retention destroyed 42 old token versions and left
version 43 as the only active version. Next work: monitor Zepp/Garmin
authentication and decide whether to remove the still-present
`GARMIN_EMAIL`/`GARMIN_PASSWORD` fallback.

## Feature index

| ID | Title | Status | Notes |
|----|-------|--------|-------|
| HS-001 | Create project harness and PRD | done | notes/HS-001-harness-and-prd.md |
| HS-002 | Add canonical WeightMeasurement model | done | notes/HS-002-weight-model.md |
| HS-003 | Add adapter interfaces | done | notes/HS-003-adapter-interfaces.md |
| HS-004 | Add Zepp Life weight source | done | notes/HS-004-zepp-life-source.md |
| HS-005 | Add sync state for duplicate prevention | done | notes/HS-005-sync-state.md |
| HS-006 | Add dry-run destination | done | notes/HS-006-dry-run-destination.md |
| HS-007 | Add Garmin weight destination | done | notes/HS-007-garmin-destination.md |
| HS-008 | Run Zepp Life source POC | done | notes/HS-008-zepp-life-poc.md |
| HS-009 | Add cloud function entrypoint | done | notes/HS-009-cloud-function-entrypoint.md |
| HS-010 | Run Garmin Connect weight destination POC | done | notes/HS-010-garmin-poc.md |
| HS-011 | Harden Garmin unattended auth | done | notes/HS-011-harden-garmin-auth.md |
| HS-012 | Per-feature harness memory refactor | done | notes/HS-012-per-feature-memory.md |
| HS-013 | Add ruff/mypy verification gate and CI | done | notes/HS-013-verification-gate.md |
| HS-014 | Add reproducible env bootstrap (init.sh) | done | notes/HS-014-init-sh.md |

## Cross-cutting decisions & events

- **Timezone normalization (2026-07-03):** Fixed the timezone bug found in
  review: Zepp Life epoch timestamps are now parsed as UTC-aware
  (`datetime.fromtimestamp(ts, tz=timezone.utc)`) instead of naive host-local
  time, so sync keys no longer depend on the host timezone (local UTC+7 vs
  cloud UTC). Sync keys normalize datetimes as UTC wall time without an
  offset: naive values are treated as UTC, aware values are converted to UTC
  and rendered without `+00:00`. This deliberately preserves the existing
  cloud sync keys (cloud ran with TZ=UTC, so its naive strings already equal
  UTC wall time) — no key migration and no duplicate re-upload on deploy.
  Garmin upload timestamps render as naive UTC through `_garmin_timestamp`,
  keeping the upload payload byte-identical to what the deployed cloud
  function already sends. This spans the canonical model (HS-002), the Zepp
  source (HS-004), and the Garmin destination (HS-007). Tests: 89 passed,
  including new tests for naive-vs-aware key equality, UTC epoch parsing, and
  aware-to-naive-UTC Garmin timestamps.

- **Circuit-breaker suspension policy:** If a Garmin upload or keepalive
  fails, HealthSync manually suspends Garmin in sync state and skips Garmin
  on future scheduled runs until the user clears the suspension after fixing
  credentials/session state (introduced for HS-011). Destination suspension
  stays a manual gate by design: it never expires on its own and a
  successful run does not clear it. The operational rule is to clear the
  state entry as part of every fix-and-deploy, documented in
  `docs/cloud_function.md` under "Destination Suspension (Manual Circuit
  Breaker)". The sync engine (HS-003) also stops the run on the first upload
  failure (`healthsync/sync_engine.py`) instead of attempting remaining
  measurements against a destination that already failed, still marking the
  destination suspended; unattempted measurements stay unsynced and are
  picked up by the next run after the breaker is cleared. This spans the
  sync engine (HS-003), sync state (HS-005), and the Garmin destination
  (HS-011).

- **Secret/credential policy:** Cloud runs must never fall back to Garmin
  email/password login. Tokens are refreshed locally and uploaded to Secret
  Manager; the stored-session login failure reason is logged and chained
  into the raised `GarminConfigError` (`healthsync/destinations/garmin.py`)
  so it is visible in Cloud Logging. Open policy mismatch: the deployed cloud
  function still injects `GARMIN_EMAIL` and `GARMIN_PASSWORD` secrets, so the
  email+password fallback remains technically possible in cloud; the user
  chose to keep them for now, and removing them is a candidate follow-up to
  enforce token-only cloud login. This spans the Garmin destination (HS-007,
  HS-011) and the cloud entrypoint (HS-009).

- **Deployment 2026-06-28:** Deployed `healthsync-weight-sync` to Google
  Cloud project `healthsync-84gaec` in `us-central1`, using GCS state bucket
  `healthsync-84gaec-state`, Secret Manager provider secrets, and real Garmin
  upload mode. Added Garmin session-token cache loading from Secret Manager
  and verified a real cloud upload succeeded; a second run skipped the same
  measurement via GCS duplicate state. Created Cloud Scheduler job
  `healthsync-weight-sync-every-4h` with cron `0 */4 * * *` in timezone
  `Asia/Bangkok`, replacing the initial every-6-hour schedule after
  confirming provider/API risk was still low (the first every-6-hour
  scheduled trigger had already invoked the function successfully at
  2026-06-28 18:00 Asia/Bangkok). Created Google Cloud Billing budget
  "HealthSync monthly guardrail" for project `healthsync-84gaec` at
  35 THB/month, with alerts at 50%, 90%, and 100% current spend.

- **Deployment 2026-07-01:** Added local Garmin token cache as Secret
  Manager secret `garmin-tokens-json` version 2, deployed Cloud Function
  revision `healthsync-weight-sync-00007-bek`, and configured the function to
  read `GARMIN_TOKENS_JSON` from `latest` plus persist refreshed tokens back
  through `GARMIN_TOKENS_SECRET_ID=garmin-tokens-json`. Granted
  `healthsync-runner@healthsync-84gaec.iam.gserviceaccount.com` Secret
  Manager read and secret-version-add permissions on `garmin-tokens-json`.
  Manually triggered the deployed scheduler job once after deployment: the
  run succeeded with one fetched measurement, one Garmin upload, no
  keepalive failure, and no destination suspension; GCS sync state then
  contained two synced weight keys and an empty `destination_suspensions`
  object.

- **Deployment 2026-07-03:** Deployed the merged hardening + timezone work to
  Cloud Function `healthsync-weight-sync` (us-central1, healthsync-84gaec)
  from local `main` at `e57a8d4`. Function state ACTIVE, update time
  2026-07-03T03:18:18Z. Pre-deploy check per the circuit-breaker rule: GCS
  sync state had no `destination_suspensions` and 4 synced keys. Manually
  triggered the scheduler job once after deployment. Result: HTTP 200,
  fetched 1, skipped 1 as duplicate, uploaded 0, keepalive succeeded, no
  suspension. The skipped sync key matched a pre-deploy key, confirming the
  timezone fix preserved existing cloud sync keys (no duplicate re-upload).

- **Deployment 2026-07-03 (harness advancement):** Deployed the merged
  harness-advancement work (HS-012 per-feature memory, HS-013 ruff/mypy/CI
  gate, HS-014 `init.sh`) to Cloud Function `healthsync-weight-sync`
  (us-central1, healthsync-84gaec) from local `main` at `7278d55`. The only
  runtime-code changes were behavior-preserving (ruff reformat,
  `timezone.utc`→`UTC` alias, mypy annotations, and a runtime-identical
  `google.cloud.storage` import form in `state.py`); sync keys and Garmin
  payloads are byte-unchanged. Source-only redeploy preserving existing env
  vars, secrets, service account, memory, and timeout. New revision
  `healthsync-weight-sync-00009-ced`, state ACTIVE, update time
  2026-07-03T08:44:45Z. Pre-deploy check per the circuit-breaker rule: GCS
  sync state had no `destination_suspensions` and 5 synced keys. Triggered
  the scheduler job once after deployment. Result: HTTP 200, uploaded 1, no
  keepalive, `destination_suspended: false`. Added `.superpowers/` and
  `docs/superpowers/` to `.gcloudignore` so agent scaffolding is not shipped
  to the function.

- **Deployment 2026-08-15 (Garmin token retention):** Granted
  `roles/secretmanager.secretVersionManager` on only `garmin-tokens-json` to
  `healthsync-runner`, committed HS-011 retention as `5a56666`, and deployed a
  source-only update to Cloud Function revision
  `healthsync-weight-sync-00010-zih`. State is ACTIVE with 100% traffic; the
  existing 512 MiB memory, 120-second timeout, service account, environment,
  secrets, and scheduler configuration were preserved. Pre-deploy GCS state
  had 47 synced keys and no destination suspension. A subsequent user-approved
  manual scheduler run completed with HTTP 200: fetched 1, skipped 1 duplicate,
  uploaded 0, keepalive 1, failed 0, and no destination suspension. Secret
  retention destroyed versions 1-42 and retained version 43 as the sole active
  `garmin-tokens-json` version; GCS state remained at 47 synced keys with no
  suspension.
