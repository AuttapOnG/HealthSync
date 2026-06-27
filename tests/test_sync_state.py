from datetime import datetime, timezone
import json

from healthsync.models import WeightMeasurement
from healthsync.state import FileSyncState
from healthsync.sync_engine import WeightSyncEngine


def make_measurement(weight_kg: float = 72.5) -> WeightMeasurement:
    return WeightMeasurement(
        source="test_source",
        measured_at=datetime(2026, 6, 27, 9, 30, tzinfo=timezone.utc),
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


class FailingDestination:
    def __init__(self) -> None:
        self.seen: list[WeightMeasurement] = []

    def upload_weight_measurement(self, measurement: WeightMeasurement) -> None:
        self.seen.append(measurement)
        raise RuntimeError("provider rejected upload")


def test_file_sync_state_marks_measurement_synced(tmp_path) -> None:
    measurement = make_measurement()
    state = FileSyncState(tmp_path / "sync_state.json")

    state.mark_synced(measurement.sync_key)

    assert state.is_synced(measurement.sync_key)


def test_sync_engine_skips_duplicate_measurements(tmp_path) -> None:
    measurement = make_measurement()
    state = FileSyncState(tmp_path / "sync_state.json")
    state.mark_synced(measurement.sync_key)
    destination = RecordingWeightDestination()

    result = WeightSyncEngine(
        FakeWeightSource([measurement]),
        destination,
        sync_state=state,
    ).sync_weight_measurements()

    assert destination.uploaded == []
    assert result.fetched_count == 1
    assert result.uploaded_count == 0
    assert result.skipped_count == 1
    assert result.skipped_sync_keys == (measurement.sync_key,)


def test_failed_upload_is_not_marked_synced(tmp_path) -> None:
    measurement = make_measurement()
    state = FileSyncState(tmp_path / "sync_state.json")
    destination = FailingDestination()

    result = WeightSyncEngine(
        FakeWeightSource([measurement]),
        destination,
        sync_state=state,
    ).sync_weight_measurements()

    assert destination.seen == [measurement]
    assert not state.is_synced(measurement.sync_key)
    assert result.uploaded_count == 0
    assert result.failed_count == 1
    assert result.failed_sync_keys == (measurement.sync_key,)


def test_file_sync_state_loads_and_saves_state(tmp_path) -> None:
    measurement = make_measurement()
    state_path = tmp_path / "nested" / "sync_state.json"

    FileSyncState(state_path).mark_synced(measurement.sync_key)
    reloaded = FileSyncState(state_path)

    assert reloaded.is_synced(measurement.sync_key)
    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "synced_weight_keys": [measurement.sync_key]
    }


def test_file_sync_state_loads_utf8_bom_file(tmp_path) -> None:
    measurement = make_measurement()
    state_path = tmp_path / "sync_state.json"
    state_path.write_text(
        json.dumps({"synced_weight_keys": [measurement.sync_key]}),
        encoding="utf-8-sig",
    )

    state = FileSyncState(state_path)

    assert state.is_synced(measurement.sync_key)
