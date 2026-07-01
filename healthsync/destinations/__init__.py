"""Destination adapter interfaces and implementations."""

from healthsync.destinations.base import KeepaliveDestination, WeightDestination
from healthsync.destinations.dry_run import DryRunWeightDestination
from healthsync.destinations.garmin import (
    GarminAuthenticationError,
    GarminConfig,
    GarminConfigError,
    GarminDestinationError,
    GarminUploadError,
    GarminWeightDestination,
)

__all__ = [
    "DryRunWeightDestination",
    "GarminAuthenticationError",
    "GarminConfig",
    "GarminConfigError",
    "GarminDestinationError",
    "GarminUploadError",
    "GarminWeightDestination",
    "KeepaliveDestination",
    "WeightDestination",
]
