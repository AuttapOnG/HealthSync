# HS-005 Add sync state for duplicate prevention

Status: done · Branch: -

## Decisions

- Should v0.1 sync only the latest measurement or all unsynced historical
  records? Open question, not yet resolved.
- GCS sync state writes use `if_generation_match` optimistic concurrency. A
  conflicting concurrent run fails fast with a clear error instead of
  silently clobbering state.

## Completed

- Completed HS-005 file-based sync state for duplicate prevention. Added
  `FileSyncState` with default local ignored path `data/sync_state.json` and
  optional `HEALTHSYNC_SYNC_STATE_PATH`, integrated optional state into
  `WeightSyncEngine`, skipped already synced weight measurements, and marked
  only successful uploads as synced. Added tests for mark synced, duplicate
  skip, failed-upload behavior, and load/save state. Verified with
  `python -m pytest` and `python -m compileall healthsync scripts`.
- After the first live local end-to-end run (see HS-007 notes), file sync
  state loading was fixed to accept UTF-8 BOM files produced by some Windows
  tooling.
- `CloudStorageSyncState` (the GCS-backed variant added for HS-009, see
  `harness/notes/HS-009-cloud-function-entrypoint.md`) tracks blob generation
  on load and passes `if_generation_match` on save; a `PreconditionFailed`
  becomes a clear "modified by another run" error (`healthsync/state.py`).

## Remaining risk / dead-ends

- Should v0.1 sync only the latest measurement or all unsynced historical
  records? Still an open design question.
- The generation captured at state load is held for the whole run; a very
  slow run overlapping another writer will fail its final save by design
  (fail fast, no retry).
