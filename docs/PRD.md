# HealthSync PRD

## 1. Summary

HealthSync is a small, extensible health data sync service. The first release focuses only on syncing body weight measurements into Garmin Connect, while the architecture remains ready for additional sources, destinations, and health metrics later.

Initial product direction:

- Start with weight sync.
- Treat Garmin Connect as the first destination.
- Keep source and destination integrations pluggable.
- Use a canonical internal model before mapping data to any provider.
- Prefer local execution first, then add cloud deployment once the sync path is proven.

## 2. Problem

Users may record body weight in one ecosystem, such as Zepp Life or a Xiaomi scale, while using Garmin Connect as their main health dashboard. Manual entry is repetitive, easy to forget, and makes long-term tracking incomplete.

HealthSync should reduce that friction by syncing validated weight measurements from a source provider into a destination provider.

## 3. Goals

- Sync body weight measurements into Garmin Connect.
- Prevent duplicate uploads for the same measurement.
- Keep provider-specific logic isolated in adapters.
- Make it easy to add future sources, such as Zepp Life, Withings, Fitbit, Google Fit, or Health Connect.
- Make it easy to add future destinations without rewriting sync logic.
- Support local development through environment variables and simple CLI commands.
- Keep v0.1 small enough to validate quickly.

## 4. Non-Goals

- Do not implement sleep, activity, heart rate, readiness, or wellness sync in v0.1.
- Do not build a frontend dashboard in v0.1.
- Do not require a database for v0.1 unless file-based state is insufficient.
- Do not couple the core sync engine directly to Garmin Connect.
- Do not attempt broad multi-provider support before the first weight sync works end to end.

## 5. Users

Primary user:

- A Garmin Connect user who records weight in another app or device ecosystem and wants the weight data reflected in Garmin.

Secondary user:

- A developer or AI coding agent extending HealthSync with new source or destination adapters.

## 6. Initial Scope

Version: v0.1

Metric:

- Body weight only.

Source:

- Use the Zepp Life user-owned app session path confirmed by the POC.
- Do not build a file, CSV, or export-based source fallback for v0.1.

Destination:

- Garmin Connect.

Runtime:

- Local CLI first.
- Google Cloud Functions HTTP trigger later, after the core sync is stable.

## 7. Core Concepts

### 7.1 Canonical Model

All source adapters must normalize provider data into a shared internal model before syncing.

Initial model:

```python
WeightMeasurement(
    source: str,
    measured_at: datetime,
    weight_kg: float,
    body_fat_percent: float | None = None,
    muscle_mass_kg: float | None = None,
    metadata: dict[str, Any] = {},
)
```

### 7.2 Source Adapter

A source adapter fetches measurements and returns canonical models.

Example sources:

- `zepp_life`
- `withings`
- `google_fit`
- `health_connect`

### 7.3 Destination Adapter

A destination adapter uploads canonical models to a target provider.

Example destinations:

- `garmin`
- `dry_run`

### 7.4 Sync Engine

The sync engine coordinates:

- Fetch measurements from a source.
- Validate and normalize records.
- Check sync state to avoid duplicates.
- Upload unsynced records to a destination.
- Mark successful uploads as synced.

The sync engine must not contain provider-specific API logic.

## 8. Functional Requirements

### FR-001: Fetch Weight Measurements

The system must fetch one or more weight measurements from a configured source adapter.

Acceptance criteria:

- Source returns a list of `WeightMeasurement` objects.
- Invalid or incomplete records are rejected with clear logs.
- The sync engine does not know source-specific API details.

### FR-002: Upload Weight To Destination

The system must upload unsynced weight measurements to the configured destination adapter.

Acceptance criteria:

- Destination receives canonical `WeightMeasurement` objects.
- Garmin-specific mapping lives only inside the Garmin adapter.
- Failed uploads are logged and are not marked as synced.

### FR-003: Prevent Duplicate Sync

The system must avoid uploading the same measurement more than once.

Acceptance criteria:

- Each measurement has a stable sync key derived from source, timestamp, metric type, and value.
- Successfully uploaded records are persisted in sync state.
- Re-running the sync does not duplicate already synced measurements.

### FR-004: Local Configuration

The system must support local execution with environment variables.

Acceptance criteria:

- `.env` is supported for local development.
- `.env.example` documents required variables.
- Secrets are never committed.

### FR-005: Extensible Adapters

The system must allow new source or destination adapters without changing the core sync engine.

Acceptance criteria:

- Adapters implement small, documented interfaces.
- Adding a new source should not require editing destination code.
- Adding a new destination should not require editing source code.

## 9. Non-Functional Requirements

- Keep dependencies minimal.
- Prefer explicit logs over silent failure.
- Keep source and destination credentials separate.
- Treat external APIs as unreliable and wrap network calls in clear error handling.
- Make local testing possible without live destination credentials by using a dry-run destination.

## 10. Proposed Repository Structure

```text
HealthSync/
|-- AGENTS.md
|-- README.md
|-- harness/
|   |-- README.md
|   |-- feature_list.json
|   `-- progress.md
|-- docs/
|   `-- PRD.md
|-- healthsync/
|   |-- __init__.py
|   |-- models.py
|   |-- sync_engine.py
|   |-- state.py
|   |-- sources/
|   |   |-- __init__.py
|   |   |-- base.py
|   |   `-- zepp_life.py
|   `-- destinations/
|       |-- __init__.py
|       |-- base.py
|       `-- garmin.py
|-- data/
|   `-- sync_state.json
|-- tests/
`-- requirements.txt
```

## 11. Milestones

### M1: Harness And Scope

- Add PRD.
- Add agent instructions.
- Add feature list.
- Add progress log.

### M2: Local Weight Sync Skeleton

- Run Zepp Life source POC.
- Document the selected source path.
- Add canonical `WeightMeasurement`.
- Add source and destination protocols.
- Add Zepp Life source adapter.
- Add dry-run destination.
- Add duplicate prevention with file state.

### M3: Garmin Destination

- Add Garmin Connect authentication.
- Upload weight measurement to Garmin.
- Handle auth and upload errors.
- Keep dry-run mode available.

### M4: Zepp Life Source Adapter

- Implement adapter for the chosen path.

### M5: Cloud Entrypoint

- Add HTTP function wrapper.
- Reuse existing sync engine.
- Add deployment notes.

## 12. Open Questions

- Should Zepp Life source sync only the profile latest weight when records are empty, or should it fail clearly?
- Should v0.1 sync only the latest weight measurement or all unsynced historical records?
- Should sync state be file-based only, or should cloud deployment use a managed store?
- What is the expected schedule: manual run, daily schedule, or webhook-like trigger?
