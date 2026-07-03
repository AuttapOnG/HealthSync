# HS-002 Add canonical WeightMeasurement model

Status: done · Branch: -

## Decisions

- None beyond the architecture decision recorded in HS-001 (source adapter ->
  canonical model -> destination adapter).

## Completed

- Completed HS-002 canonical weight model. Added `healthsync.models.WeightMeasurement`
  with source, measured timestamp, weight, optional body composition fields,
  metadata, validation, and a stable duplicate-detection sync key. Added
  `tests/test_models.py` and `requirements-dev.txt` for pytest-based tests.

## Remaining risk / dead-ends

- None known. See the cross-cutting "Timezone normalization" entry in
  `harness/progress.md` for a later fix to how this model's sync key handles
  naive vs. aware datetimes.
