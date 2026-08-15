# HS-011 Harden Garmin unattended auth

Status: done · Branch: `fix/HS-011-garmin-secret-version-retention`

## Decisions

- Garmin session tokens may refresh more often than expected, so cloud runs
  should avoid overwriting a warm refreshed token cache with stale
  `GARMIN_TOKENS_JSON`.
- When `GARMIN_TOKENS_SECRET_ID` is configured, the Garmin destination
  should persist a changed `garmin_tokens.json` back to Secret Manager as a
  new secret version after successful authentication.
- If a Garmin run only finds measurements that were already synced,
  HealthSync should make one read-only keepalive request instead of posting
  duplicate weight data, so cached DI tokens can refresh even on no-op sync
  days.
- If a Garmin upload or keepalive fails, HealthSync should manually suspend
  Garmin in sync state and skip Garmin on future scheduled runs until the
  user clears the suspension after fixing credentials/session state. (The
  general policy that this suspension never auto-clears and must be cleared
  on every fix-and-deploy is cross-cutting; see the "Circuit-breaker
  suspension policy" entry in `harness/progress.md`.)

## Completed

- Updated Garmin session hydration to leave an existing token cache file
  intact instead of overwriting it from environment-provided token JSON on
  every run.
- Added optional Secret Manager persistence for refreshed Garmin token cache
  JSON, plus tests for config parsing, no-overwrite hydration, and
  persistence dispatch.
- Limited persisted Garmin token history to one active Secret Manager version.
  Each persistence attempt now destroys versions older than the retained latest
  version, including cleanup when token JSON is unchanged. Versions newer than
  the retained version are never destroyed, protecting overlapping invocations.
  Cloud IAM now also requires Secret Version Manager on the token secret.
- Granted `roles/secretmanager.secretVersionManager` on only
  `garmin-tokens-json` to the deployed `healthsync-runner` service account on
  2026-08-15. The existing Secret Accessor and Secret Version Adder bindings
  were left unchanged; no token versions were destroyed and no deployment was
  performed as part of the IAM update.
- Committed the retention fix as `5a56666` and deployed it source-only on
  2026-08-15 as Cloud Function revision
  `healthsync-weight-sync-00010-zih`. The revision is ACTIVE with all traffic
  and preserves the existing runtime configuration. A user-approved manual
  scheduler run returned HTTP 200 with one duplicate skipped, a successful
  keepalive, no upload or failure, and no destination suspension. Cleanup
  destroyed token versions 1-42 and retained version 43 as the only active
  version.
- After verifying version 2 was enabled and latest for the three static
  provider secrets, permanently destroyed historical version 1 of
  `garmin-email`, `garmin-password`, and `zepp-app-token` with user approval.
  The old values differed from version 2 and are not recoverable. The project
  now has four active Secret Manager versions in total, one per secret.
- Documented `GARMIN_TOKENS_SECRET_ID` and `GARMIN_TOKENS_SECRET_PROJECT` in
  `.env.example` and `docs/cloud_function.md`.
- Added a generic destination keepalive hook. The sync engine calls it once
  when a real run skips all fetched measurements as duplicates and performs
  no uploads; Garmin implements the hook with a read-only profile request.
- Added explicit keepalive success/failure logging and included keepalive
  counters in local/cloud sync results.
- Added manual Garmin destination suspension state. Upload or keepalive
  failure marks Garmin suspended; future runs return a skipped/suspended
  result without fetching source data or touching Garmin until the state
  entry is removed.
- Committed the Garmin token refresh hardening work as
  `0ca5424 Harden Garmin token refresh handling` and merged it into `main`
  as `10169a8 Merge Garmin token refresh hardening`.

## Remaining risk / dead-ends

- The deployed Cloud Function service account may need additional Secret
  Manager permissions before token persistence can work reliably in
  production.
