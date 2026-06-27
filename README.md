# HealthSync

HealthSync is a pluggable health data sync project. The first version focuses on syncing body weight measurements into Garmin Connect while keeping the architecture ready for future sources and destinations.

See `docs/PRD.md` for the current product scope and `harness/feature_list.json` for the implementation queue.

For AI or agent work, start with `AGENTS.md` and `harness/README.md`.

## Current Status

Harness and PRD are in place. Implementation has not started yet.

## Initial Direction

```text
Source Adapter -> Canonical Model -> Destination Adapter
```

Initial metric:

- Weight

Initial destination:

- Garmin Connect

Initial source strategy:

- File-based import first
- Zepp Life once the data extraction path is confirmed
