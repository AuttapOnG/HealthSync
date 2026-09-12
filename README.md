# HealthSync

HealthSync is a pluggable health data sync project. The first version focuses on syncing body weight measurements into Garmin Connect while keeping the architecture ready for future sources and destinations.

See `docs/PRD.md` for the current product scope and `harness/feature_list.json` for the implementation queue.

For AI or agent work, start with `AGENTS.md` and `harness/README.md`.

## Current Status

Harness and PRD are in place. HS-008 has a Zepp Life source POC documented in
`docs/zepp_life_source_poc.md`, with project-local MCP notes in
`docs/zepp_life_mcp_poc.md`. Local weight sync can run through the Zepp Life
source, file sync state, and either a dry-run or Garmin destination.

## Initial Direction

```text
Source Adapter -> Canonical Model -> Destination Adapter
```

Initial metric:

- Weight

Initial destination:

- Garmin Connect

Initial source strategy:

- Zepp Life user-owned app session
- No file, CSV, or export-based source fallback in v0.1

## Setup

The fastest way to get a working environment is the bootstrap script:

```bash
bash init.sh
```

`init.sh` is idempotent (safe to re-run), creates a `.venv`, upgrades pip, and
installs `requirements.txt`, `requirements-dev.txt`, and
`requirements-poc.txt`, then prints next steps. It never prints or commits
secrets. If the POC git-based dependency in `requirements-poc.txt` cannot be
resolved in a network-restricted environment, the runtime and dev installs
still complete; see `harness/notes/HS-014-init-sh.md` for details.

## Local Weight Sync

Install runtime dependencies for the local runner or Cloud Functions entrypoint:

```powershell
python -m pip install -r requirements.txt
```

Install development dependencies for tests:

```powershell
python -m pip install -r requirements-dev.txt
```

Install POC/runtime provider dependencies before using the Garmin destination:

```powershell
python -m pip install -r requirements-poc.txt
```

Configure local environment variables in `.env` using `.env.example` as the
template. Keep `.env`, session tokens, and `.local/garmin-session/` private.

Safe dry-run mode is the default and does not upload to Garmin:

```powershell
python scripts/sync_weight.py
```

Dry-run mode does not mark measurements as synced, so a later Garmin run can
still upload the same measurement after you confirm it.

The Garmin destination floors weight to one decimal place in kg before upload
(for example, 96.95 becomes 96.9). Source values and duplicate-detection keys
keep their original precision. Already synced records are not rewritten.

To upload to Garmin, both confirmations are required in the same runtime:

```powershell
$env:HEALTHSYNC_ALLOW_REAL_UPLOAD="true"
python scripts/sync_weight.py --destination garmin --allow-real-upload
```

Without both the environment gate and the command flag, the runner refuses to
create a real Garmin destination.

## Cloud Function

The HTTP-triggered Google Cloud Functions target is:

```text
main.sync_weight_http
```

It reuses the same Zepp source, Garmin destination, sync state, and sync engine
as the local runner. See `docs/cloud_function.md` for local
`functions-framework` commands and cloud environment variables.
