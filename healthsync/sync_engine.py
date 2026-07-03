"""Core sync coordination that depends only on adapter interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging

from healthsync.destinations import KeepaliveDestination, WeightDestination
from healthsync.models import WeightMeasurement
from healthsync.sources import WeightSource
from healthsync.state import DestinationSuspensionState, SyncState


@dataclass(frozen=True, slots=True)
class WeightSyncResult:
    """Summary of a weight sync run."""

    fetched_count: int
    uploaded_count: int
    failed_count: int
    skipped_count: int = 0
    keepalive_count: int = 0
    keepalive_failed: bool = False
    destination_suspended: bool = False
    destination_suspension_reason: str | None = None
    failed_sync_keys: tuple[str, ...] = field(default_factory=tuple)
    skipped_sync_keys: tuple[str, ...] = field(default_factory=tuple)


class WeightSyncEngine:
    """Coordinate weight sync without provider-specific behavior."""

    def __init__(
        self,
        source: WeightSource,
        destination: WeightDestination,
        *,
        sync_state: SyncState | None = None,
        destination_name: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._source = source
        self._destination = destination
        self._sync_state = sync_state
        self._destination_name = destination_name
        self._logger = logger or logging.getLogger(__name__)

    def sync_weight_measurements(self) -> WeightSyncResult:
        """Fetch canonical measurements and upload each one to the destination."""

        suspension = self._active_destination_suspension()
        if suspension is not None:
            self._logger.warning(
                "Destination is manually suspended; skipping provider calls",
                extra={
                    "destination": suspension.destination,
                    "reason": suspension.reason,
                },
            )
            return WeightSyncResult(
                fetched_count=0,
                uploaded_count=0,
                failed_count=0,
                destination_suspended=True,
                destination_suspension_reason=suspension.reason,
            )

        measurements = self._source.fetch_weight_measurements()
        uploaded_count = 0
        failed_sync_keys: list[str] = []
        skipped_sync_keys: list[str] = []

        for measurement in measurements:
            if self._sync_state is not None and self._sync_state.is_synced(
                measurement.sync_key
            ):
                skipped_sync_keys.append(measurement.sync_key)
                continue

            try:
                self._destination.upload_weight_measurement(measurement)
            except Exception:
                failed_sync_keys.append(measurement.sync_key)
                self._mark_destination_suspended("upload failed")
                self._logger.exception(
                    "Failed to upload weight measurement; stopping this run",
                    extra={
                        "source": measurement.source,
                        "sync_key": measurement.sync_key,
                    },
                )
                break

            if self._sync_state is not None:
                self._sync_state.mark_synced(measurement.sync_key)
            uploaded_count += 1

        keepalive_count = 0
        keepalive_failed = False
        if (
            uploaded_count == 0
            and not failed_sync_keys
            and skipped_sync_keys
            and isinstance(self._destination, KeepaliveDestination)
        ):
            try:
                self._logger.info(
                    "Keeping destination session alive after duplicate-only sync",
                    extra={"skipped_count": len(skipped_sync_keys)},
                )
                self._destination.keepalive()
                keepalive_count = 1
                self._logger.info("Destination keepalive succeeded")
            except Exception:
                keepalive_failed = True
                self._mark_destination_suspended("keepalive failed")
                self._logger.exception("Failed to keep destination session alive")

        return WeightSyncResult(
            fetched_count=len(measurements),
            uploaded_count=uploaded_count,
            failed_count=len(failed_sync_keys),
            skipped_count=len(skipped_sync_keys),
            keepalive_count=keepalive_count,
            keepalive_failed=keepalive_failed,
            failed_sync_keys=tuple(failed_sync_keys),
            skipped_sync_keys=tuple(skipped_sync_keys),
        )

    def _active_destination_suspension(self):
        if (
            self._destination_name is None
            or self._sync_state is None
            or not isinstance(self._sync_state, DestinationSuspensionState)
        ):
            return None
        return self._sync_state.get_destination_suspension(self._destination_name)

    def _mark_destination_suspended(self, reason: str) -> None:
        if (
            self._destination_name is None
            or self._sync_state is None
            or not isinstance(self._sync_state, DestinationSuspensionState)
        ):
            return
        self._sync_state.mark_destination_suspended(
            self._destination_name,
            reason=reason,
        )


__all__ = ["WeightSyncEngine", "WeightSyncResult"]
