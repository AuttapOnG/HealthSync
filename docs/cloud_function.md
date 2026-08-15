# Google Cloud Function Entrypoint

HealthSync exposes an HTTP-triggered Cloud Functions entrypoint at:

```text
main.sync_weight_http
```

The entrypoint reuses the existing source adapter, destination adapter, sync
state, and `WeightSyncEngine`. It defaults to `dry-run` so local function tests
cannot upload to Garmin unless you explicitly opt in.

## Local Functions Framework

Install runtime dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run the HTTP function locally:

```powershell
functions-framework --target sync_weight_http
```

Then trigger it:

```powershell
Invoke-RestMethod -Method Post http://localhost:8080
```

For a local dry-run, configure the Zepp variables and leave:

```powershell
$env:HEALTHSYNC_DESTINATION="dry-run"
```

For a real Garmin upload through the function, both variables are required:

```powershell
$env:HEALTHSYNC_DESTINATION="garmin"
$env:HEALTHSYNC_ALLOW_REAL_UPLOAD="true"
```

## Cloud Environment

Required Zepp Life source variables:

```text
ZEPP_HOST
ZEPP_USER_ID
ZEPP_APP_TOKEN
ZEPP_DAYS
```

Required Garmin destination variables for real uploads:

```text
HEALTHSYNC_DESTINATION=garmin
HEALTHSYNC_ALLOW_REAL_UPLOAD=true
GARMIN_SESSION_DIR=/tmp/garmin-session
GARMIN_EMAIL
GARMIN_PASSWORD
GARMIN_TOKENS_JSON
GARMIN_TOKENS_SECRET_ID
GARMIN_TOKENS_SECRET_PROJECT
GARMIN_VERIFY_UPLOADS=false
```

Required duplicate-prevention state variables for Cloud Storage:

```text
HEALTHSYNC_STATE_BACKEND=gcs
HEALTHSYNC_GCS_STATE_BUCKET=<bucket-name>
HEALTHSYNC_GCS_STATE_BLOB=healthsync/sync_state.json
```

Use Secret Manager or your deployment system's secret injection for Zepp and
Garmin secrets. Do not commit `.env`, Garmin session files, provider tokens, or
captured provider responses.

`GARMIN_TOKENS_JSON` is optional but recommended for cloud runs when Garmin MFA
is enabled. Store the contents of local `.local/garmin-session/garmin_tokens.json`
in Secret Manager, then inject it as `GARMIN_TOKENS_JSON`. The function writes
that value to `/tmp/garmin-session/garmin_tokens.json` before Garmin login.

`GARMIN_TOKENS_SECRET_ID` is optional but recommended for unattended scheduled
runs. When set, HealthSync reads the post-login token cache from
`GARMIN_SESSION_DIR/garmin_tokens.json` and writes it back to Secret Manager as
a new version if it changed. After each persistence attempt, HealthSync destroys
older active token versions so only the latest version remains billable. Set
`GARMIN_TOKENS_SECRET_PROJECT` when the Google Cloud project cannot be inferred
from application default credentials. The function service account needs
permission to access, list, add, and destroy versions on that secret. Grant
`roles/secretmanager.secretVersionManager` and
`roles/secretmanager.secretAccessor` on the individual token secret rather than
at project level.

When a scheduled Garmin run fetches only measurements that were already synced,
HealthSync makes one read-only Garmin keepalive request instead of posting a
duplicate weight. This gives `python-garminconnect` a chance to refresh cached
DI tokens and lets HealthSync persist the refreshed token cache when Secret
Manager persistence is configured.

If a Garmin upload or keepalive request fails, HealthSync stores a manual
Garmin suspension in the configured sync state. Later scheduled runs skip Garmin
without fetching source data or touching Garmin again until the suspension is
manually removed from state. To resume, remove the `garmin` entry under
`destination_suspensions` from the local state file or the GCS state object
after refreshing/fixing Garmin credentials.

## State Backend

Cloud Functions should use `CloudStorageSyncState` through
`HEALTHSYNC_STATE_BACKEND=gcs`. Local CLI runs can keep using the file backend
with `HEALTHSYNC_SYNC_STATE_PATH`.

The GCS object uses the same JSON shape as local file state:

```json
{
  "synced_weight_keys": []
}
```

## Destination Suspension (Manual Circuit Breaker)

When an upload or keepalive to a destination fails, the sync engine marks that
destination as suspended in the sync state:

```json
{
  "synced_weight_keys": [],
  "destination_suspensions": {
    "garmin": {
      "manual": true,
      "reason": "upload failed"
    }
  }
}
```

While suspended, every later run skips all provider calls and returns
`destination_suspended: true` in the sync result. This is an intentional
manual gate: the suspension never expires on its own, and a successful run
does not clear it. A failing destination stays paused until a human looks at
the failure.

**Operational rule: after fixing the root cause and deploying, clear the
circuit breaker as part of the deploy.** Remove the destination's entry from
`destination_suspensions` in the sync state, then trigger or wait for the next
scheduled run and confirm the result no longer reports
`destination_suspended: true`.

For the GCS backend:

```powershell
gsutil cp gs://<state-bucket>/healthsync/sync_state.json sync_state.json
# Edit sync_state.json: delete the "garmin" entry (or the whole
# "destination_suspensions" object), then write it back.
gsutil cp sync_state.json gs://<state-bucket>/healthsync/sync_state.json
```

For the local file backend, edit the file at `HEALTHSYNC_SYNC_STATE_PATH`
(default `data/sync_state.json`) the same way. Do not remove entries from
`synced_weight_keys` while doing this — that would re-upload old measurements.

## Scheduler

The deployed function can be triggered every four hours with Cloud Scheduler:

```powershell
gcloud scheduler jobs create http healthsync-weight-sync-every-4h `
  --location=us-central1 `
  --schedule="0 */4 * * *" `
  --time-zone="Asia/Bangkok" `
  --uri="https://healthsync-weight-sync-qwxh5idy5q-uc.a.run.app" `
  --http-method=POST `
  --oidc-service-account-email="healthsync-runner@healthsync-84gaec.iam.gserviceaccount.com" `
  --oidc-token-audience="https://healthsync-weight-sync-qwxh5idy5q-uc.a.run.app"
```

The service account also needs `roles/run.invoker` on the underlying Cloud Run
service.
