from datetime import UTC, datetime

import pytest

from healthsync.destinations import WeightDestination
from healthsync.models import WeightMeasurement
from healthsync.sources import WeightSource
from healthsync.sync_engine import WeightSyncEngine


def make_measurement(weight_kg: float = 72.5) -> WeightMeasurement:
    return WeightMeasurement(
        source="test_source",
        measured_at=datetime(2026, 6, 27, 9, 30, tzinfo=UTC),
        weight_kg=weight_kg,
    )


class FakeWeightSource:
    def __init__(self, measurements: list[WeightMeasurement]) -> None:
        self.measurements = measurements

    def fetch_weight_measurements(self) -> list[WeightMeasurement]:
        return self.measurements


class RecordingWeightDestination:
    def __init__(self) -> None:
        self.uploaded: list[WeightMeasurement] = []

    def upload_weight_measurement(self, measurement: WeightMeasurement) -> None:
        self.uploaded.append(measurement)


class FailingOnceDestination:
    def __init__(self) -> None:
        self.seen: list[WeightMeasurement] = []

    def upload_weight_measurement(self, measurement: WeightMeasurement) -> None:
        self.seen.append(measurement)
        if len(self.seen) == 1:
            raise RuntimeError("provider rejected upload")


def test_adapters_structurally_match_weight_interfaces() -> None:
    source = FakeWeightSource([make_measurement()])
    destination = RecordingWeightDestination()

    assert isinstance(source, WeightSource)
    assert isinstance(destination, WeightDestination)


def test_sync_engine_uploads_measurements_through_interfaces() -> None:
    measurements = [make_measurement(72.5), make_measurement(72.8)]
    source = FakeWeightSource(measurements)
    destination = RecordingWeightDestination()

    result = WeightSyncEngine(source, destination).sync_weight_measurements()

    assert destination.uploaded == measurements
    assert result.fetched_count == 2
    assert result.uploaded_count == 2
    assert result.failed_count == 0
    assert result.failed_sync_keys == ()


def test_sync_engine_logs_failed_upload_and_stops(
    caplog: pytest.LogCaptureFixture,
) -> None:
    measurements = [make_measurement(72.5), make_measurement(72.8)]
    source = FakeWeightSource(measurements)
    destination = FailingOnceDestination()

    with caplog.at_level("ERROR", logger="healthsync.sync_engine"):
        result = WeightSyncEngine(source, destination).sync_weight_measurements()

    assert destination.seen == [measurements[0]]
    assert result.fetched_count == 2
    assert result.uploaded_count == 0
    assert result.failed_count == 1
    assert result.failed_sync_keys == (measurements[0].sync_key,)
    assert "Failed to upload weight measurement" in caplog.text
