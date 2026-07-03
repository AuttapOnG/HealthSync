"""Google Cloud Functions HTTP entrypoint for HealthSync weight sync."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from healthsync.destinations import DryRunWeightDestination, GarminWeightDestination
from healthsync.sources import ZeppLifeWeightSource
from healthsync.state import SyncState, build_sync_state_from_env
from healthsync.sync_engine import WeightSyncEngine, WeightSyncResult


DESTINATION_ENV_VAR = "HEALTHSYNC_DESTINATION"
REAL_UPLOAD_ENV_VAR = "HEALTHSYNC_ALLOW_REAL_UPLOAD"
LOGGER = logging.getLogger(__name__)


def sync_weight_http(request: Any) -> tuple[str, int, dict[str, str]]:
    """Run weight sync from an HTTP-triggered Cloud Function."""

    method = getattr(request, "method", "GET")
    if method not in {"GET", "POST"}:
        return _json_response({"error": "Method not allowed"}, status=405)

    try:
        result = run_weight_sync_from_env()
    except Exception:
        LOGGER.exception("HealthSync weight sync failed")
        return _json_response(
            {"error": "HealthSync weight sync failed; see Cloud Logging for details"},
            status=500,
        )

    status = 200 if result.failed_count == 0 and not result.keepalive_failed else 502
    log_sync_result(result, status=status)
    return _json_response(result_to_payload(result), status=status)


def run_weight_sync_from_env() -> WeightSyncResult:
    """Build adapters from environment variables and run the sync engine."""

    destination_name = os.environ.get(DESTINATION_ENV_VAR, "dry-run").strip().lower()
    destination = build_destination_from_env(destination_name)
    sync_state = build_cloud_sync_state(destination_name)

    return WeightSyncEngine(
        ZeppLifeWeightSource.from_env(),
        destination,
        sync_state=sync_state,
        destination_name=destination_name,
    ).sync_weight_measurements()


def build_destination_from_env(
    destination_name: str,
) -> DryRunWeightDestination | GarminWeightDestination:
    """Create the configured destination for cloud execution."""

    if destination_name == "dry-run":
        return DryRunWeightDestination()

    if destination_name != "garmin":
        raise ValueError(f"Unsupported destination: {destination_name}")

    if os.environ.get(REAL_UPLOAD_ENV_VAR, "").strip().lower() != "true":
        raise ValueError(
            "Refusing Garmin upload: set HEALTHSYNC_DESTINATION=garmin and "
            "HEALTHSYNC_ALLOW_REAL_UPLOAD=true"
        )

    return GarminWeightDestination.from_env()


def build_cloud_sync_state(destination_name: str) -> SyncState | None:
    """Use durable sync state for real uploads, but no state for dry-run."""

    if destination_name == "dry-run":
        return None
    return build_sync_state_from_env()


def result_to_payload(result: WeightSyncResult) -> dict[str, Any]:
    """Convert a sync result into an HTTP JSON payload."""

    return {
        "fetched_count": result.fetched_count,
        "uploaded_count": result.uploaded_count,
        "failed_count": result.failed_count,
        "skipped_count": result.skipped_count,
        "keepalive_count": result.keepalive_count,
        "keepalive_failed": result.keepalive_failed,
        "destination_suspended": result.destination_suspended,
        "destination_suspension_reason": result.destination_suspension_reason,
        "failed_sync_keys": list(result.failed_sync_keys),
        "skipped_sync_keys": list(result.skipped_sync_keys),
    }


def log_sync_result(result: WeightSyncResult, *, status: int) -> None:
    """Write sync counters to Cloud Logging for scheduled-run inspection."""

    print(
        json.dumps(
            {
                "severity": "INFO",
                "message": "HealthSync weight sync result",
                "http_status": status,
                "fetched_count": result.fetched_count,
                "uploaded_count": result.uploaded_count,
                "failed_count": result.failed_count,
                "skipped_count": result.skipped_count,
                "keepalive_count": result.keepalive_count,
                "keepalive_failed": result.keepalive_failed,
                "destination_suspended": result.destination_suspended,
                "destination_suspension_reason": result.destination_suspension_reason,
                "failed_sync_keys": list(result.failed_sync_keys),
                "skipped_sync_keys": list(result.skipped_sync_keys),
            },
            sort_keys=True,
        ),
        flush=True,
    )


def _json_response(
    payload: dict[str, Any],
    *,
    status: int,
) -> tuple[str, int, dict[str, str]]:
    return (
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        status,
        {"Content-Type": "application/json"},
    )
