# HS-008 Run Zepp Life source POC

Status: done · Branch: -

## Decisions

- After user feedback, selected a user-owned Zepp Life app session as the
  preferred live POC path, using captured `apptoken`, user id, and regional
  host for read-only weight records.

## Completed

- Completed HS-008 Zepp Life source POC. Added
  `docs/zepp_life_source_poc.md`, `scripts/zepp_life_login_weight_poc.py`,
  `scripts/zepp_life_weight_poc.py`, and non-private sample files.
- Added `zepp-life-mcp` into the project as pinned POC/reference tooling via
  `requirements-poc.txt` and `docs/zepp_life_mcp_poc.md`. This gives a
  project-local way to test Zepp cloud session and export-file modes without
  making the HealthSync runtime depend on MCP yet.
- Live Zepp/Huami privacy-page session test reached `api-mifit.huami.com`.
  `weightRecords` returned an empty list, but `GET /users/{user_id}` returned
  a profile-level latest weight, so the HealthSync login POC fell back to
  profile weight when records are empty. This fallback behavior was later
  implemented in the real source adapter (see
  `harness/notes/HS-004-zepp-life-source.md`).
- Created a local ignored `.env` for Zepp POC credentials and updated
  `scripts/zepp_life_login_weight_poc.py` to load `.env` automatically.

## Remaining risk / dead-ends

- Zepp Life app-session access is unofficial and tokens can expire; see
  `harness/notes/HS-004-zepp-life-source.md` for the resulting ongoing risk
  in the real source adapter.
