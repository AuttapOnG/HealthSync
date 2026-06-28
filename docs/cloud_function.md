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
