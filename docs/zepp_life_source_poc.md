# Zepp Life Source POC

Date: 2026-06-27

## Decision

Prefer a user-owned Zepp Life app session as the first live POC path, because
the user wants to log in to Zepp Life directly and read their own latest weight
without waiting for an export. Keep Zepp Life personal data export as the
stable fallback path.

Direct login/session path:

1. Log in through the Zepp/Huami privacy page or official Zepp Life app.
2. Extract `apptoken`, user id, and region/host from the user-owned session.
4. Read latest weight with `GET /users/{id}/members/-1/weightRecords`.
5. Normalize it into the future `WeightMeasurement` model.

Important: this is an unofficial, read-only path based on the mobile API. The
POC must not commit tokens, raw proxy captures, cookies, or account details.

Export fallback path:

1. Request a Zepp Life / Mi Fit personal data export.
2. Download and unpack the generated archive locally.
3. Read the newest weight row from `BODY/BODY_*.csv`.
4. Normalize it into the future `WeightMeasurement` model.

Fallback path:

- Keep HS-004 file import as the universal fallback.
- If the Zepp Life export is missing body data for the user's account, bridge
  Zepp Life to Google Fit or Health Connect, then import a local export from
  that bridge.

## Paths Investigated

### 1. User-owned Zepp Life app session

Evidence:

- `zepp-life-mcp` documents two supported modes, `cloud_session` and
  `export_file`, and includes body measurements in its current data coverage.
- `zepp-life-mcp` documents browser login through
  `https://user.huami.com/privacy2/index.html`, extracting the `apptoken`
  cookie, then configuring a cloud session with token, user id, and region.
- Community tooling documents Zepp/Huami mobile API reads with an `apptoken`,
  regional `api-mifit*.zepp.com` host, and user id captured from the official
  logged-in app session.
- The relevant weight endpoint is documented by community tooling as
  `GET /users/{id}/members/-1/weightRecords`.
- The same tooling warns that password-based login is not currently supported
  and that older plaintext login paths are unreliable or deprecated.

Why this is now the preferred live POC:

- It matches the user's preference to log in to Zepp Life directly.
- It can fetch recent weight without waiting for a manual export.
- It can stay outside the sync engine as a Zepp source adapter later.

Setup steps:

1. Install the project POC dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements-poc.txt
   ```

2. Follow `docs/zepp_life_mcp_poc.md` to configure `zepp-life-mcp` using the
   `apptoken` from `https://user.huami.com/privacy2/index.html`.
3. If using HealthSync's tiny direct script, save these values locally only:
   - `apptoken` as `ZEPP_APP_TOKEN`
   - user id as `ZEPP_USER_ID`
   - API host as `ZEPP_HOST`, such as `api-mifit.huami.com`
4. Put those values in local `.env` or set them in the shell, then run:

   ```powershell
   python scripts/zepp_life_login_weight_poc.py
   ```

Limitations and risks:

- This is not an official public API.
- Tokens expire and must be refreshed by logging in/capturing again.
- Region matters; use the account's actual region or host.
- Browser cookies, proxy captures, and tool state can contain sensitive data and
  must never be committed.
- This should remain read-only until the endpoint behavior is well understood.

### 2. Zepp Life personal data export

Evidence:

- Xiaomi / Mi Fit GDPR export tooling and examples describe an archive
  containing folders such as `BODY/` with `BODY_*.csv` files.
- Zepp privacy support documents account and privacy-management flows inside
  the Zepp Life app.
- Zepp Life supports Xiaomi weighing scale products, which is the data family
  HealthSync needs for v0.1.

Why this stays as fallback:

- It is local and testable without a long-running unofficial cloud session.
- It does not require HealthSync to store Zepp credentials, cookies, or tokens.
- The implementation can reuse the planned file source shape.
- It gives historical records, not only the latest live scale reading.

Setup steps:

1. In Zepp Life, open the privacy/account management area and request/export
   account data.
2. Download the archive when Zepp/Xiaomi provides it.
3. Unpack the archive into a local private directory, or pass the `.zip` to the
   POC script.
4. Confirm a `BODY/` folder exists and contains `BODY_*.csv`.
5. Run:

   ```powershell
   python scripts/zepp_life_weight_poc.py --input path\to\export.zip
   ```

Limitations and risks:

- Export generation can be delayed and may require manual account steps.
- Archive filenames and CSV column names may vary by region, app version, or
  account age.
- The export may be password protected; HealthSync should not handle or store
  that password beyond a local manual unzip step.
- This is not near-real-time sync. It is a robust import path first.

### 3. Zepp Life to Google Fit / Health Connect bridge

Evidence:

- Zepp Life can be linked to Google Fit through the app's account-linking flow
  on Android.
- Android Health Connect provides a central place to grant app permissions and
  share health data between apps.
- Google Fit data can be exported through Google Takeout.

Why this is fallback instead of primary:

- Health Connect access is Android-app centered, not a simple local Python
  source for HealthSync.
- Google Fit / Takeout introduces another provider and an export format that
  may differ from Zepp's original weight records.
- Some users report intermittent third-party sync behavior, so it is best kept
  as a fallback bridge.

### 4. Zepp Life to Mi Fitness transfer

Evidence:

- Xiaomi documents a Mi Fitness transfer flow from Zepp Life and lists weight
  as one of the transferred data types.
- Xiaomi also documents a Mi Fitness cloud export flow from the Xiaomi account
  privacy area.

Why this is fallback:

- It adds another app and account export step.
- It may be useful if Zepp Life export access fails, but it is not simpler than
  reading the Zepp export directly.

## Tiny POC

`zepp-life-mcp` is included as a project POC dependency in
`requirements-poc.txt`, with setup notes in `docs/zepp_life_mcp_poc.md`.

The script at `scripts/zepp_life_login_weight_poc.py` reads either:

- a live Zepp app session through `ZEPP_HOST`, `ZEPP_USER_ID`, and
  `ZEPP_APP_TOKEN`,
- a profile-level latest weight from `GET /users/{user_id}` if
  `weightRecords` is empty, or
- a saved mock JSON response via `--mock-response`.

Run the mock:

```powershell
python scripts/zepp_life_login_weight_poc.py --mock-response data\samples\zepp_life_weight_api_response.json
```

The fallback export script at `scripts/zepp_life_weight_poc.py` reads either:

- a Zepp export `.zip`,
- an unpacked Zepp export directory,
- a direct `BODY_*.csv` file, or
- the bundled sample via `--sample`.

It emits a small JSON record shaped like the future canonical model:

```json
{
  "source": "zepp_life_export",
  "measured_at": "2026-06-27T07:15:00+07:00",
  "weight_kg": 72.4,
  "body_fat_percent": 18.6,
  "metadata": {
    "raw_file": "BODY/BODY_sample.csv",
    "raw_row_number": 3
  }
}
```

Run the sample:

```powershell
python scripts/zepp_life_weight_poc.py --sample
```

## Implementation Plan Update

- HS-002 should keep `WeightMeasurement` small and allow optional body
  composition fields.
- A future Zepp source adapter should start as
  `healthsync/sources/zepp_life_api.py` with explicit token/host configuration
  and read-only weight fetching.
- `zepp-life-mcp` should remain POC/reference tooling until HealthSync has its
  own adapter boundary. Do not make the core sync engine depend on MCP.
- HS-004 should still support Zepp export CSV as a fallback file shape.
- HealthSync should not store Zepp password, raw proxy captures, cookies, or
  committed tokens. If tokens are used locally, they belong in `.env` only.
- Garmin upload work can proceed once the file source proves the canonical
  weight model and duplicate key behavior.

## Sources

- Zepp Life app listing, supported Xiaomi scale product families:
  https://play.google.com/store/apps/details?id=com.xiaomi.hm.health
- Zepp privacy support:
  https://www.zepp.com/privacy-support
- Xiaomi Mi Fitness transfer from Zepp Life, including weight:
  https://www.mi.com/global/support/faq/details/KA-231328/
- Xiaomi Mi Fitness export flow:
  https://www.mi.com/global/support/article/KA-11566/
- Example Mi Fit / Zepp export archive layout with `BODY/BODY_*.csv`:
  https://github.com/zoilomora/xiaomi-mi-fit-data-export
- Community Zepp mobile API CLI documenting captured `apptoken`, regional host,
  and weight endpoint:
  https://github.com/m4ary/zepp-health-cli
- Zepp Life MCP server listing:
  https://mcpmarket.com/server/zepp-life
- Zepp Life MCP repository:
  https://github.com/kubulashvili/zepp-life-mcp
- Google Fit export through Google Takeout:
  https://support.google.com/fit/answer/3024190
- Android Health Connect setup:
  https://support.google.com/android/answer/12201227
