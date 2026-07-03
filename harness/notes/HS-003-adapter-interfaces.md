# HS-003 Add adapter interfaces

Status: done · Branch: -

## Decisions

- None beyond the architecture decision recorded in HS-001 (source adapter ->
  canonical model -> destination adapter).

## Completed

- Completed HS-003 adapter interfaces. Added source and destination protocols
  for weight measurements, plus a small `WeightSyncEngine` that fetches
  canonical measurements from a source and uploads them through a destination
  without provider-specific logic. Added tests using fake adapters to verify
  structural interface use, upload coordination, and failed-upload logging.

## Remaining risk / dead-ends

- None known. Later engine changes (fail-fast on first upload failure,
  destination keepalive hook, manual suspension) are cross-cutting and
  recorded in `harness/progress.md`'s "Cross-cutting decisions & events"
  section, since they span the engine plus the sync-state and Garmin
  destination features.
