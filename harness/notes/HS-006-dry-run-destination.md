# HS-006 Add dry-run destination

Status: done · Branch: -

## Decisions

- None beyond the general Garmin-upload-safety decisions recorded in HS-007
  and HS-009 (dry-run is the default unless a real destination and explicit
  opt-in flags are set).

## Completed

- Completed HS-006 dry-run destination. Added `DryRunWeightDestination` under
  `healthsync/destinations/` to record canonical measurements that would be
  uploaded without credentials or external API calls. Added tests covering
  the destination interface, stored would-upload measurements, and sync
  engine use.
- After the first live local end-to-end run (see HS-007 notes), dry-run was
  fixed to no longer persist sync state.

## Remaining risk / dead-ends

- None known.
