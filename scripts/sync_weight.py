"""Local Zepp Life weight sync runner.

The default destination is dry-run. A real Garmin upload requires both:

    HEALTHSYNC_ALLOW_REAL_UPLOAD=true
    python scripts/sync_weight.py --destination garmin --allow-real-upload
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from healthsync.destinations import DryRunWeightDestination, GarminWeightDestination
from healthsync.models import WeightMeasurement
from healthsync.sources import ZeppLifeWeightSource
from healthsync.state import FileSyncState, SyncState
from healthsync.sync_engine import WeightSyncEngine, WeightSyncResult


REAL_UPLOAD_ENV_VAR = "HEALTHSYNC_ALLOW_REAL_UPLOAD"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination",
        choices=("dry-run", "garmin"),
        default="dry-run",
        help="Destination adapter to use. Defaults to safe dry-run mode.",
    )
    parser.add_argument(
        "--allow-real-upload",
        action="store_true",
        help="Required with HEALTHSYNC_ALLOW_REAL_UPLOAD=true before Garmin upload.",
    )
    args = parser.parse_args()
    load_dotenv()

    try:
        destination = build_destination(args.destination, args.allow_real_upload)
        dry_run_destination = (
            destination if isinstance(destination, DryRunWeightDestination) else None
        )
        result = run_sync(destination, sync_state=build_sync_state(args.destination))
    except Exception as exc:
        print(f"HealthSync local weight sync failed: {exc}", file=sys.stderr)
        return 1

    payload: dict[str, Any] = {
        "destination": args.destination,
        "fetched_count": result.fetched_count,
        "uploaded_count": result.uploaded_count,
        "failed_count": result.failed_count,
        "skipped_count": result.skipped_count,
        "failed_sync_keys": list(result.failed_sync_keys),
        "skipped_sync_keys": list(result.skipped_sync_keys),
    }
    if dry_run_destination is not None:
        payload["would_upload"] = [
            measurement_to_dict(measurement)
            for measurement in dry_run_destination.uploaded_measurements
        ]

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result.failed_count == 0 else 1


def build_destination(
    destination_name: str,
    allow_real_upload_flag: bool,
) -> DryRunWeightDestination | GarminWeightDestination:
    if destination_name == "dry-run":
        return DryRunWeightDestination()

    if destination_name != "garmin":
        raise ValueError(f"Unsupported destination: {destination_name}")

    if not real_upload_allowed(allow_real_upload_flag):
        raise ValueError(
            "Refusing Garmin upload: set HEALTHSYNC_ALLOW_REAL_UPLOAD=true and pass "
            "--allow-real-upload in the command"
        )

    return GarminWeightDestination.from_env()


def build_sync_state(destination_name: str) -> SyncState | None:
    if destination_name == "dry-run":
        return None
    return FileSyncState.from_env()


def run_sync(
    destination: DryRunWeightDestination | GarminWeightDestination,
    *,
    sync_state: SyncState | None,
) -> WeightSyncResult:
    return WeightSyncEngine(
        ZeppLifeWeightSource.from_env(),
        destination,
        sync_state=sync_state,
    ).sync_weight_measurements()


def real_upload_allowed(allow_real_upload_flag: bool) -> bool:
    return allow_real_upload_flag and os.environ.get(REAL_UPLOAD_ENV_VAR, "").lower() == "true"


def measurement_to_dict(measurement: WeightMeasurement) -> dict[str, Any]:
    return {
        "source": measurement.source,
        "measured_at": measurement.measured_at.isoformat(),
        "weight_kg": measurement.weight_kg,
        "body_fat_percent": measurement.body_fat_percent,
        "muscle_mass_kg": measurement.muscle_mass_kg,
        "sync_key": measurement.sync_key,
    }


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


if __name__ == "__main__":
    raise SystemExit(main())
