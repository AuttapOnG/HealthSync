"""Core sync coordination that depends only on adapter interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging

from healthsync.destinations import WeightDestination
from healthsync.models import WeightMeasurement
from healthsync.sources import WeightSource
from healthsync.state import SyncState


@dataclass(frozen=True, slots=True)
class WeightSyncResult:
    """Summary of a weight sync run."""

    fetched_count: int
    uploaded_count: int
    failed_count: int
    skipped_count: int = 0
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
        logger: logging.Logger | None = None,
    ) -> None:
        self._source = source
        self._destination = destination
        self._sync_state = sync_state
        self._logger = logger or logging.getLogger(__name__)

    def sync_weight_measurements(self) -> WeightSyncResult:
        """Fetch canonical measurements and upload each one to the destination."""

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
                self._logger.exception(
                    "Failed to upload weight measurement",
                    extra={
                        "source": measurement.source,
                        "sync_key": measurement.sync_key,
                    },
                )
                continue

            if self._sync_state is not None:
                self._sync_state.mark_synced(measurement.sync_key)
            uploaded_count += 1

        return WeightSyncResult(
            fetched_count=len(measurements),
            uploaded_count=uploaded_count,
            failed_count=len(failed_sync_keys),
            skipped_count=len(skipped_sync_keys),
            failed_sync_keys=tuple(failed_sync_keys),
            skipped_sync_keys=tuple(skipped_sync_keys),
        )


__all__ = ["WeightSyncEngine", "WeightSyncResult"]
