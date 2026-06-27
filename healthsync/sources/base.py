"""Base interfaces for HealthSync source adapters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from healthsync.models import WeightMeasurement


@runtime_checkable
class WeightSource(Protocol):
    """Adapter that fetches canonical body weight measurements."""

    def fetch_weight_measurements(self) -> list[WeightMeasurement]:
        """Return canonical weight measurements ready for syncing."""
