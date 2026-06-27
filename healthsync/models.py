"""Canonical data models used between HealthSync adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from typing import Any


def _normalize_datetime(value: datetime) -> str:
    if not isinstance(value, datetime):
        raise ValueError("measured_at must be a datetime")

    normalized = value
    if normalized.tzinfo is not None:
        normalized = normalized.astimezone(timezone.utc)

    return normalized.isoformat(timespec="seconds")


def _validate_optional_number(
    name: str,
    value: float | int | None,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be a number or None")
    if not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and float(value) < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    if maximum is not None and float(value) > maximum:
        raise ValueError(f"{name} must be at most {maximum}")


@dataclass(frozen=True, slots=True)
class WeightMeasurement:
    """Canonical body weight measurement passed between adapters."""

    source: str
    measured_at: datetime
    weight_kg: float
    body_fat_percent: float | None = None
    muscle_mass_kg: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    metric_type: str = field(default="weight", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source is required")

        _normalize_datetime(self.measured_at)

        if isinstance(self.weight_kg, bool) or not isinstance(self.weight_kg, int | float):
            raise ValueError("weight_kg must be a number")
        if not math.isfinite(float(self.weight_kg)) or float(self.weight_kg) <= 0:
            raise ValueError("weight_kg must be a positive finite number")

        _validate_optional_number(
            "body_fat_percent",
            self.body_fat_percent,
            minimum=0,
            maximum=100,
        )
        _validate_optional_number("muscle_mass_kg", self.muscle_mass_kg, minimum=0)

        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dict")

        object.__setattr__(self, "source", self.source.strip())
        object.__setattr__(self, "weight_kg", float(self.weight_kg))
        if self.body_fat_percent is not None:
            object.__setattr__(self, "body_fat_percent", float(self.body_fat_percent))
        if self.muscle_mass_kg is not None:
            object.__setattr__(self, "muscle_mass_kg", float(self.muscle_mass_kg))
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def sync_key(self) -> str:
        """Stable key for duplicate detection across sync runs."""

        payload = {
            "source": self.source,
            "metric_type": self.metric_type,
            "measured_at": _normalize_datetime(self.measured_at),
            "weight_kg": f"{self.weight_kg:.3f}",
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return sha256(encoded.encode("utf-8")).hexdigest()
