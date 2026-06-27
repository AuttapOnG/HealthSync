"""Destination adapter interfaces and implementations."""

from healthsync.destinations.base import WeightDestination
from healthsync.destinations.dry_run import DryRunWeightDestination

__all__ = ["DryRunWeightDestination", "WeightDestination"]
