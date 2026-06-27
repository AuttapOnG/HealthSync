"""Garmin Connect weight destination POC.

This script checks Garmin Connect authentication and shows the exact plain
weight upload mapping selected for HealthSync. It never uploads by default.

Examples:
    python scripts/garmin_weight_poc.py --dry-run-only
    python scripts/garmin_weight_poc.py --check-auth
    python scripts/garmin_weight_poc.py --weight-kg 72.3 --measured-at 2026-06-27T08:30:00

Real upload requires both:
    --allow-upload --confirm-weight-kg <same weight>
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from healthsync.models import WeightMeasurement


DEFAULT_SESSION_DIR = ".local/garmin-session"


@dataclass(frozen=True)
class GarminWeightMapping:
    measurement: WeightMeasurement
    method: str
    args: dict[str, Any]
    supported_plain_weight_fields: list[str]
    supported_body_composition_fields: list[str]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "measurement": {
                "source": self.measurement.source,
                "measured_at": self.measurement.measured_at.isoformat(),
                "weight_kg": self.measurement.weight_kg,
                "body_fat_percent": self.measurement.body_fat_percent,
                "muscle_mass_kg": self.measurement.muscle_mass_kg,
                "sync_key": self.measurement.sync_key,
            },
            "method": self.method,
            "args": self.args,
            "supported_plain_weight_fields": self.supported_plain_weight_fields,
            "supported_body_composition_fields": self.supported_body_composition_fields,
            "safety": "dry-run; no upload unless --allow-upload and --confirm-weight-kg match",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weight-kg", type=float, default=72.5)
    parser.add_argument(
        "--measured-at",
        default=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        help="Measurement timestamp, ideally ISO 8601.",
    )
    parser.add_argument("--body-fat-percent", type=float)
    parser.add_argument("--muscle-mass-kg", type=float)
    parser.add_argument(
        "--check-auth",
        action="store_true",
        help="Authenticate against Garmin Connect. Does not upload by itself.",
    )
    parser.add_argument(
        "--dry-run-only",
        action="store_true",
        help="Only print mapping and supported fields; skip auth even if credentials exist.",
    )
    parser.add_argument(
        "--allow-upload",
        action="store_true",
        help="Permit a real Garmin upload when confirmation also matches.",
    )
    parser.add_argument(
        "--confirm-weight-kg",
        type=float,
        help="Must exactly match --weight-kg before a real upload is attempted.",
    )
    args = parser.parse_args()
    load_dotenv()

    try:
        measurement = WeightMeasurement(
            source="garmin_weight_poc",
            measured_at=parse_datetime(args.measured_at),
            weight_kg=args.weight_kg,
            body_fat_percent=args.body_fat_percent,
            muscle_mass_kg=args.muscle_mass_kg,
            metadata={"poc": "HS-010"},
        )
    except ValueError as exc:
        print(f"Invalid sample WeightMeasurement: {exc}", file=sys.stderr)
        return 2

    try:
        mapping = build_mapping(measurement)
    except ImportError as exc:
        print(f"Garmin POC dependency missing: {exc}", file=sys.stderr)
        print("Install POC dependencies with: python -m pip install -r requirements-poc.txt", file=sys.stderr)
        return 2

    print(json.dumps(mapping.to_json_dict(), indent=2, sort_keys=True))

    should_upload = args.allow_upload or args.confirm_weight_kg is not None
    if args.dry_run_only and (args.check_auth or should_upload):
        print("--dry-run-only cannot be combined with auth or upload flags.", file=sys.stderr)
        return 2

    if args.dry_run_only:
        return 0

    if should_upload and not upload_confirmed(args.weight_kg, args.allow_upload, args.confirm_weight_kg):
        print(
            "Refusing upload: pass --allow-upload and --confirm-weight-kg equal to --weight-kg.",
            file=sys.stderr,
        )
        return 2

    if not args.check_auth and not should_upload:
        print("Dry run complete. Pass --check-auth to verify Garmin login.")
        return 0

    try:
        api = login_to_garmin()
    except GarminPOCError as exc:
        print(f"Garmin authentication failed: {exc}", file=sys.stderr)
        return 1

    print("Garmin authentication succeeded.")

    if not should_upload:
        return 0

    try:
        result = api.add_weigh_in(**mapping.args)
    except Exception as exc:  # Library-specific exceptions are imported lazily.
        print(f"Garmin weight upload failed: {exc}", file=sys.stderr)
        return 1

    print("Garmin weight upload succeeded.")
    print(json.dumps({"upload_result": result}, indent=2, sort_keys=True, default=str))
    return 0


def build_mapping(measurement: WeightMeasurement) -> GarminWeightMapping:
    from garminconnect import Garmin

    plain_fields = list(inspect.signature(Garmin.add_weigh_in).parameters)
    body_fields = list(inspect.signature(Garmin.add_body_composition).parameters)
    plain_fields = [field for field in plain_fields if field != "self"]
    body_fields = [field for field in body_fields if field != "self"]

    return GarminWeightMapping(
        measurement=measurement,
        method="Garmin.add_weigh_in",
        args={
            "weight": measurement.weight_kg,
            "unitKey": "kg",
            "timestamp": measurement.measured_at.isoformat(),
        },
        supported_plain_weight_fields=plain_fields,
        supported_body_composition_fields=body_fields,
    )


def login_to_garmin() -> Any:
    try:
        from garminconnect import (
            Garmin,
            GarminConnectAuthenticationError,
            GarminConnectConnectionError,
            GarminConnectTooManyRequestsError,
        )
    except ImportError as exc:
        raise GarminPOCError(
            "garminconnect is not installed; run python -m pip install -r requirements-poc.txt"
        ) from exc

    session_dir = Path(
        os.environ.get("GARMIN_SESSION_DIR")
        or os.environ.get("GARMINTOKENS")
        or DEFAULT_SESSION_DIR
    )
    tokenstore = str(session_dir)

    try:
        api = Garmin()
        api.login(tokenstore)
        return api
    except (FileNotFoundError, GarminConnectAuthenticationError, GarminConnectConnectionError):
        pass
    except GarminConnectTooManyRequestsError as exc:
        raise GarminPOCError(f"rate limited by Garmin: {exc}") from exc

    email = require_env("GARMIN_EMAIL")
    password = require_env("GARMIN_PASSWORD")
    session_dir.mkdir(parents=True, exist_ok=True)

    try:
        api = Garmin(
            email=email,
            password=password,
            prompt_mfa=prompt_mfa,
        )
        api.login(tokenstore)
        return api
    except GarminConnectTooManyRequestsError as exc:
        raise GarminPOCError(f"rate limited by Garmin: {exc}") from exc
    except GarminConnectAuthenticationError as exc:
        raise GarminPOCError(f"invalid credentials, MFA failure, or expired session: {exc}") from exc
    except GarminConnectConnectionError as exc:
        raise GarminPOCError(f"connection or Garmin API error: {exc}") from exc


def prompt_mfa() -> str:
    return input("Garmin MFA/2FA code: ").strip()


def upload_confirmed(weight_kg: float, allow_upload: bool, confirm_weight_kg: float | None) -> bool:
    return bool(allow_upload and confirm_weight_kg is not None and confirm_weight_kg == weight_kg)


def parse_datetime(value: str) -> datetime:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("measured-at is required")
    return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value or value.startswith("replace-with-"):
        raise GarminPOCError(f"missing required environment variable: {name}")
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


class GarminPOCError(Exception):
    """Expected Garmin POC setup, auth, or connection failure."""


if __name__ == "__main__":
    raise SystemExit(main())
