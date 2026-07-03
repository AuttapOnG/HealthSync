# HS-007 Add Garmin weight destination

Status: done · Branch: -

## Decisions

- Run a Garmin Connect destination POC before implementing the full Garmin
  adapter because Garmin authentication, 2FA, and weight upload behavior
  needed confirmation (see HS-010).

## Completed

- Completed HS-007 Garmin weight destination. Added
  `healthsync/destinations/garmin.py` with environment/injectable
  configuration, token-session login first, credential fallback, canonical
  weight/body-composition mapping, and clear config/auth/upload errors. Added
  fake-client tests for Garmin mapping, configuration validation,
  authentication failure, upload failure, and failed-upload sync-state
  behavior.
- Added local runner in `scripts/sync_weight.py`. It defaults to dry-run,
  wires `ZeppLifeWeightSource` through `FileSyncState` into dry-run or
  Garmin, and refuses Garmin uploads unless
  `HEALTHSYNC_ALLOW_REAL_UPLOAD=true` and `--allow-real-upload` are both
  present in the runtime command.
- After the first live local end-to-end run, Garmin showed the synced
  `107.4 kg` value, confirming the local runner, Zepp source, sync state, and
  Garmin destination worked together end to end. That run also surfaced the
  dry-run and file-sync-state fixes recorded in HS-006 and HS-005.
- Added optional Garmin read-back verification after weight upload. The
  Garmin destination can now read weight records for the uploaded
  measurement date, convert Garmin read-back grams to kg, and raise a clear
  verification error when no matching weight is found so sync state is not
  marked synced. The behavior defaults off via `GARMIN_VERIFY_UPLOADS=false`
  to avoid extra real Garmin reads unless explicitly enabled.

## Remaining risk / dead-ends

- Garmin upload verification still depends on unofficial Garmin Connect read
  endpoints and may need adjustment if `python-garminconnect` changes the
  `get_weigh_ins` response shape or signature.
- Garmin upload accepts kg with `unitKey="kg"`, while read-back weight values
  are grams (confirmed during the HS-010 POC, see
  `harness/notes/HS-010-garmin-poc.md`); this asymmetry must be preserved in
  any future changes to mapping or verification code.
