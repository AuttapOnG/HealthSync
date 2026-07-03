# HS-004 Add Zepp Life weight source

Status: done · Branch: -

## Decisions

- None specific beyond HS-001/HS-008 direction (Zepp Life user-owned app
  session as the confirmed source path).

## Completed

- Completed HS-004 Zepp Life weight source adapter. Added
  `healthsync/sources/zepp_life.py` with environment/injectable session
  configuration, read-only `weightRecords` fetching, profile latest-weight
  fallback when records are empty, canonical `WeightMeasurement` mapping, and
  clear errors for invalid responses or missing configuration. Added
  `tests/test_zepp_life_source.py` for mapping, empty records, fallback,
  invalid responses, and config validation. Documented optional `ZEPP_DAYS` in
  `.env.example`. Verified with `python -m pytest` and
  `python -m compileall healthsync scripts`.
- The profile latest-weight fallback behavior was first confirmed live during
  the HS-008 POC (see `harness/notes/HS-008-zepp-life-poc.md`), where
  `weightRecords` returned empty but `GET /users/{user_id}` returned a
  profile-level latest weight; that fallback was then implemented here.

## Remaining risk / dead-ends

- Zepp Life app-session access is unofficial and tokens can expire; both
  local and cloud runs depend on a valid user-owned `ZEPP_APP_TOKEN`,
  `ZEPP_USER_ID`, and regional `ZEPP_HOST`.
- Zepp Life date strings without timezone info (the format in the sample
  payload) are parsed naive and interpreted as UTC by the sync key. If real
  Zepp string data turns out to be local wall time, Garmin will show that
  wall time as-is; acceptable for now. See the cross-cutting "Timezone
  normalization" entry in `harness/progress.md` for the related epoch-parsing
  fix.
