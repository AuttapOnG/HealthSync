"""Read the latest Zepp Life weight record from a user-owned app session.

This POC intentionally does not implement Zepp email/password login. Current
community tooling points to Zepp/Huami app sessions captured from your own
logged-in session as the practical route. Provide the session through `.env` or
environment variables:

    ZEPP_HOST=api-mifit.huami.com
    ZEPP_USER_ID=1234567890
    ZEPP_APP_TOKEN=...

Use --mock-response to validate parsing without a live token.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class LoginPOCWeightRecord:
    measured_at: datetime
    weight_kg: float
    raw_record: dict[str, Any]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "source": "zepp_life_api",
            "measured_at": self.measured_at.isoformat(),
            "weight_kg": self.weight_kg,
            "body_fat_percent": first_float(
                self.raw_record,
                ("fat", "bodyFat", "body_fat", "bodyFatRate", "body_fat_percent"),
            ),
            "muscle_mass_kg": first_float(
                self.raw_record,
                ("muscle", "muscleMass", "muscle_mass", "muscle_mass_kg"),
            ),
            "metadata": {
                "provider": "zepp_life",
                "path": "GET /users/{user_id}/members/-1/weightRecords or GET /users/{user_id}",
                "raw_keys": sorted(self.raw_record.keys()),
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mock-response",
        type=Path,
        help="Path to a saved JSON response for parser validation.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Lookback window for the live API request.",
    )
    args = parser.parse_args()
    load_dotenv()

    try:
        payload = (
            json.loads(args.mock_response.read_text(encoding="utf-8"))
            if args.mock_response
            else fetch_live_weight_records(args.days)
        )
        latest = latest_weight_record(payload)
    except (KeyError, ValueError, OSError, HTTPError, URLError) as exc:
        print(f"Zepp Life login weight POC failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(latest.to_json_dict(), indent=2, sort_keys=True))
    return 0


def fetch_live_weight_records(days: int) -> Any:
    host = require_env("ZEPP_HOST").removeprefix("https://").removeprefix("http://")
    user_id = require_env("ZEPP_USER_ID")
    app_token = require_env("ZEPP_APP_TOKEN")
    headers = {
        "Apptoken": app_token,
        "Appname": "com.huami.webapp",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://user.huami.com",
        "Referer": "https://user.huami.com/",
        "User-Agent": "HealthSync/0.1",
    }

    records_url = f"https://{host}/users/{user_id}/members/-1/weightRecords?days={days}"
    records_payload = fetch_json(records_url, headers)
    if iter_record_dicts(records_payload):
        return records_payload

    # The privacy web session may expose the latest profile weight even when
    # member weightRecords are empty for the account/export selection.
    profile_url = f"https://{host}/users/{user_id}"
    return fetch_json(profile_url, headers)


def fetch_json(url: str, headers: dict[str, str]) -> Any:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise KeyError(f"Missing required environment variable: {name}")
    return value


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        name, value = stripped.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and name not in os.environ:
            os.environ[name] = value


def latest_weight_record(payload: Any) -> LoginPOCWeightRecord:
    records = list(iter_record_dicts(payload))
    parsed = [record for record in (parse_record(raw) for raw in records) if record is not None]
    if not parsed:
        raise ValueError("No parseable weight records found")
    return max(parsed, key=lambda record: record.measured_at)


def iter_record_dicts(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    for key in ("items", "data", "records", "weightRecords", "weight_records"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = iter_record_dicts(value)
            if nested:
                return nested

    if looks_like_weight_record(payload):
        return [payload]
    return []


def looks_like_weight_record(record: dict[str, Any]) -> bool:
    return first_float(record, ("weight", "weightKg", "weight_kg", "value")) is not None


def parse_record(record: dict[str, Any]) -> LoginPOCWeightRecord | None:
    measured_at = first_datetime(
        record,
        (
            "date",
            "time",
            "timestamp",
            "datetime",
            "measuredAt",
            "measureTime",
            "createdTime",
            "generatedTime",
            "lastUpdateTime",
        ),
    )
    weight_kg = first_float(record, ("weight", "weightKg", "weight_kg", "value"))
    if measured_at is None or weight_kg is None:
        return None
    return LoginPOCWeightRecord(measured_at=measured_at, weight_kg=weight_kg, raw_record=record)


def first_datetime(record: dict[str, Any], keys: tuple[str, ...]) -> datetime | None:
    for key in keys:
        value = record.get(key)
        parsed = parse_datetime(value)
        if parsed is not None:
            return parsed
    return None


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(timestamp)

    cleaned = str(value).strip()
    if not cleaned:
        return None

    for date_format in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, date_format)
        except ValueError:
            pass

    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        return None


def first_float(record: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


if __name__ == "__main__":
    raise SystemExit(main())
