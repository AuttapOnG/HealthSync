"""Base interfaces for HealthSync destination adapters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from healthsync.models import WeightMeasurement


@runtime_checkable
class WeightDestination(Protocol):
    """Adapter that uploads canonical body weight measurements."""

    def upload_weight_measurement(self, measurement: WeightMeasurement) -> None:
        """Upload one canonical weight measurement."""


@runtime_checkable
class KeepaliveDestination(Protocol):
    """Adapter that can refresh or verify its provider session without uploading."""

    def keepalive(self) -> None:
        """Make a safe provider request to keep the destination session current."""
