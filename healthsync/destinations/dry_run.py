"""Dry-run destination adapter for safe local weight sync testing."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from healthsync.models import WeightMeasurement


@dataclass(slots=True)
class DryRunWeightDestination:
    """Record measurements that would be uploaded without external side effects."""

    logger: logging.Logger | None = None
    uploaded_measurements: list[WeightMeasurement] = field(default_factory=list)

    def upload_weight_measurement(self, measurement: WeightMeasurement) -> None:
        """Record one canonical measurement as a would-upload event."""

        self.uploaded_measurements.append(measurement)
        if self.logger is not None:
            self.logger.info(
                "Dry-run weight upload",
                extra={
                    "source": measurement.source,
                    "sync_key": measurement.sync_key,
                    "measured_at": measurement.measured_at.isoformat(),
                    "weight_kg": measurement.weight_kg,
                },
            )


__all__ = ["DryRunWeightDestination"]
