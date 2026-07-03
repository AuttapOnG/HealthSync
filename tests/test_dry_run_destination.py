from datetime import UTC, datetime

from healthsync.destinations import DryRunWeightDestination, WeightDestination
from healthsync.models import WeightMeasurement
from healthsync.sync_engine import WeightSyncEngine


def make_measurement(weight_kg: float = 72.5) -> WeightMeasurement:
    return WeightMeasurement(
        source="test_source",
        measured_at=datetime(2026, 6, 27, 9, 30, tzinfo=UTC),
        weight_kg=weight_kg,
        body_fat_percent=18.2,
    )


class FakeWeightSource:
    def __init__(self, measurements: list[WeightMeasurement]) -> None:
        self.measurements = measurements

    def fetch_weight_measurements(self) -> list[WeightMeasurement]:
        return self.measurements


def test_dry_run_destination_matches_weight_destination_interface() -> None:
    destination = DryRunWeightDestination()

    assert isinstance(destination, WeightDestination)


def test_dry_run_records_measurements_without_provider_credentials() -> None:
    measurement = make_measurement()
    destination = DryRunWeightDestination()

    destination.upload_weight_measurement(measurement)

    assert destination.uploaded_measurements == [measurement]


def test_sync_engine_can_use_dry_run_destination() -> None:
    measurements = [make_measurement(72.5), make_measurement(72.8)]
    destination = DryRunWeightDestination()

    result = WeightSyncEngine(
        FakeWeightSource(measurements),
        destination,
    ).sync_weight_measurements()

    assert destination.uploaded_measurements == measurements
    assert result.fetched_count == 2
    assert result.uploaded_count == 2
    assert result.failed_count == 0
