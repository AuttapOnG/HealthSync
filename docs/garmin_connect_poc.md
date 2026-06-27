# Garmin Connect Weight Destination POC

## Summary

HS-010 investigated Garmin Connect as the first HealthSync destination for
canonical `WeightMeasurement` values. The selected v0.1 path is
`python-garminconnect` because it currently wraps Garmin authentication, token
storage, weigh-in reads, manual weigh-in upload, and body-composition FIT upload
behind a small Python API.

The POC script is `scripts/garmin_weight_poc.py`. It is safe by default:
authentication and field mapping can be tested without uploading a real weight.
An upload requires both `--allow-upload` and `--confirm-weight-kg` matching the
sample measurement.

## Live Verification

On 2026-06-27, the POC was tested against the user's Garmin Connect account
with a local `.env` and saved session tokens under `GARMIN_SESSION_DIR`.

Verified:

- Fresh login with MFA/2FA succeeded.
- Session reuse succeeded from `.local/garmin-session/garmin_tokens.json`.
- Read-only weight endpoints returned account data:
  - `get_weigh_ins(...)`
  - `get_body_composition(...)`
  - `get_daily_weigh_ins(...)`
- Historical records confirmed Garmin returns `weight` in grams, not kg:
  - 2026-02-06: `110000.0` grams, equivalent to `110.0 kg`
  - 2023-06-19: `98000.0` grams, equivalent to `98.0 kg`
- A real guarded upload succeeded for `109.0 kg` using
  `Garmin.add_weigh_in(weight=109.0, unitKey="kg", timestamp=...)`.
- Read-back for 2026-06-27 confirmed one manual entry:
  - `weight`: `109000.0` grams
  - `sourceType`: `MANUAL`
  - `samplePk`: `1782566397007`

Implementation note: the upload API accepts kg when `unitKey="kg"`, while the
read APIs return stored weight values in grams. The HS-007 adapter should
convert Garmin read-back values from grams to kg when using reads for
verification or duplicate checks.

## Investigated Paths

### python-garminconnect

Repository: https://github.com/cyberjunky/python-garminconnect

Findings:

- Auth supports stored token reuse through a token directory and fresh
  email/password login with MFA callback support.
- Weight upload is supported through `Garmin.add_weigh_in(...)`.
- Body-composition FIT upload is supported through
  `Garmin.add_body_composition(...)`.
- Existing reads include `get_weigh_ins(...)` and `get_daily_weigh_ins(...)`,
  which can be useful for later duplicate checks or verification.

Chosen for HS-007 because it provides the smallest adapter surface:

- `Garmin.login(tokenstore)`
- `Garmin.add_weigh_in(weight, unitKey="kg", timestamp=...)`
- optionally `Garmin.add_body_composition(timestamp, weight, percent_fat, muscle_mass, ...)`

### garth

Repository: https://github.com/matin/garth

Findings:

- `garth` was a lower-level Garmin SSO/OAuth client and influenced other
  Garmin community tooling.
- The maintainer now documents it as deprecated because Garmin changed the auth
  flow used by the library.
- Existing saved OAuth sessions may continue temporarily, but new logins are
  not a practical base for HealthSync v0.1.

Not chosen for HS-007.

## Authentication And Session Notes

The POC reads local settings from `.env` or environment variables:

```text
GARMIN_EMAIL=...
GARMIN_PASSWORD=...
GARMIN_SESSION_DIR=.local/garmin-session
```

`GARMIN_SESSION_DIR` is passed to `python-garminconnect` as the token store.
Do not commit this directory. It can contain reusable Garmin session tokens.

The script attempts authentication in this order:

1. Reuse tokens from `GARMIN_SESSION_DIR`.
2. If tokens are missing or invalid, use `GARMIN_EMAIL` and
   `GARMIN_PASSWORD`.
3. If Garmin requires MFA/2FA, prompt locally for a code and store the refreshed
   session after successful login.

Authentication failures are reported clearly and do not mark anything as synced.

## Weight Upload Fields

The selected upload path for plain weight is:

```python
api.add_weigh_in(weight, unitKey="kg", timestamp=timestamp)
```

Required fields:

- `weight`: positive numeric value.
- `unitKey`: `kg` or `lbs`; HealthSync should use `kg`.
- `timestamp`: ISO-like local timestamp. If omitted, the library uses the
  current time, so the HealthSync adapter should always provide the canonical
  measurement timestamp.

The library maps this to Garmin's weight service with:

- `dateTimestamp`
- `gmtTimestamp`
- `unitKey`
- `sourceType="MANUAL"`
- `value`

The body-composition path can additionally support:

- `percent_fat`
- `percent_hydration`
- `visceral_fat_mass`
- `bone_mass`
- `muscle_mass`
- `basal_met`
- `active_met`
- `physique_rating`
- `metabolic_age`
- `visceral_fat_rating`
- `bmi`

For HS-007, start with `add_weigh_in` for canonical `weight_kg`. Consider
`add_body_composition` only after confirming Garmin accepts the extra fields
from real Zepp Life records without surprising display behavior.

## Limitations And Risks

- Garmin Connect has no official public personal-sync API for this workflow;
  this depends on community-maintained reverse-engineered endpoints.
- Garmin auth flows can change and may break unattended login.
- MFA/2FA may require periodic manual intervention unless saved session tokens
  remain valid.
- Uploading the same timestamp/weight more than once may create duplicate
  entries, so HS-007 should be paired with HS-005 duplicate prevention.
- The POC intentionally does not delete test uploads.

## HS-007 Implementation Plan

- Add `healthsync/destinations/garmin.py` around `python-garminconnect`.
- Read `GARMIN_EMAIL`, `GARMIN_PASSWORD`, and `GARMIN_SESSION_DIR` from the
  environment.
- Keep Garmin-specific payload and auth handling inside the destination adapter.
- Upload canonical `WeightMeasurement.weight_kg` with `unitKey="kg"` and
  `measured_at.isoformat()`.
- Treat Garmin read-back `weight` values as grams and convert to kg before
  comparing them with canonical `WeightMeasurement.weight_kg`.
- Fail fast on missing credentials when no valid session exists.
- Catch Garmin auth/connection exceptions and report clear errors.
- Do not mark failed uploads as synced; leave that to the sync engine and state
  layer.
