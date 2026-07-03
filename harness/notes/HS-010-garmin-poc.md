# HS-010 Run Garmin Connect weight destination POC

Status: done · Branch: -

## Decisions

- Run a Garmin Connect destination POC before implementing the full Garmin
  adapter because Garmin authentication, 2FA, and weight upload behavior
  needed confirmation.
- Selected `python-garminconnect` for HS-007 because `garth` is deprecated
  and new logins are not a practical base.

## Completed

- Completed HS-010 Garmin Connect weight destination POC. Investigated
  `python-garminconnect` and `garth`. Added Garmin placeholders to
  `.env.example`, documented auth/session/2FA, upload fields, risks, and the
  HS-007 plan in `docs/garmin_connect_poc.md`, and added
  `scripts/garmin_weight_poc.py` with dry-run-first mapping, auth-check, and
  explicit double-confirmation before any real upload.
- Live Garmin verification succeeded with user-provided local credentials:
  MFA login worked, reusable session tokens were saved under the ignored
  `GARMIN_SESSION_DIR`, read-only weight endpoints returned historical
  records, and a guarded `109.0 kg` upload was confirmed by read-back as one
  2026-06-27 manual entry (`109000.0` grams).

## Remaining risk / dead-ends

- HS-007 must remember that Garmin upload accepts kg with `unitKey="kg"`,
  while read-back weight values are grams.
