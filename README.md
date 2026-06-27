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

## Local Weight Sync

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

To upload to Garmin, both confirmations are required in the same runtime:

```powershell
$env:HEALTHSYNC_ALLOW_REAL_UPLOAD="true"
python scripts/sync_weight.py --destination garmin --allow-real-upload
```

Without both the environment gate and the command flag, the runner refuses to
create a real Garmin destination.
