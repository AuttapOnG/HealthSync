from datetime import datetime, timezone
import json

import pytest

from healthsync.models import WeightMeasurement
from healthsync.state import CloudStorageSyncState, FileSyncState, build_sync_state_from_env
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


class FakeStorageBlob:
    def __init__(self, text: str | None = None) -> None:
        self.text = text
        self.uploaded_text: str | None = None
        self.content_type: str | None = None

    def exists(self) -> bool:
        return self.text is not None

    def download_as_text(self, encoding: str = "utf-8") -> str:
        return self.text or ""

    def upload_from_string(self, text: str, *, content_type: str) -> None:
        self.text = text
        self.uploaded_text = text
        self.content_type = content_type


class FakeStorageBucket:
    def __init__(self, blob: FakeStorageBlob) -> None:
        self.blob_instance = blob
        self.requested_blob_name: str | None = None

    def blob(self, blob_name: str) -> FakeStorageBlob:
        self.requested_blob_name = blob_name
        return self.blob_instance


class FakeStorageClient:
    def __init__(self, blob: FakeStorageBlob) -> None:
        self.bucket_instance = FakeStorageBucket(blob)
        self.requested_bucket_name: str | None = None

    def bucket(self, bucket_name: str) -> FakeStorageBucket:
        self.requested_bucket_name = bucket_name
        return self.bucket_instance


def test_cloud_storage_sync_state_loads_existing_keys() -> None:
    measurement = make_measurement()
    blob = FakeStorageBlob(
        json.dumps({"synced_weight_keys": [measurement.sync_key]}),
    )
    client = FakeStorageClient(blob)

    state = CloudStorageSyncState("test-bucket", "state/sync.json", client=client)

    assert state.is_synced(measurement.sync_key)
    assert client.requested_bucket_name == "test-bucket"
    assert client.bucket_instance.requested_blob_name == "state/sync.json"


def test_cloud_storage_sync_state_marks_and_saves_key() -> None:
    measurement = make_measurement()
    blob = FakeStorageBlob()
    state = CloudStorageSyncState(
        "test-bucket",
        "state/sync.json",
        client=FakeStorageClient(blob),
    )

    state.mark_synced(measurement.sync_key)

    assert state.is_synced(measurement.sync_key)
    assert blob.content_type == "application/json"
    assert json.loads(blob.uploaded_text or "{}") == {
        "synced_weight_keys": [measurement.sync_key]
    }


def test_build_sync_state_from_env_uses_gcs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blob = FakeStorageBlob()
    client = FakeStorageClient(blob)
    monkeypatch.setenv("HEALTHSYNC_STATE_BACKEND", "gcs")
    monkeypatch.setenv("HEALTHSYNC_GCS_STATE_BUCKET", "healthsync-state")
    monkeypatch.setenv("HEALTHSYNC_GCS_STATE_BLOB", "sync.json")
    monkeypatch.setattr("healthsync.state._default_storage_client", lambda: client)

    state = build_sync_state_from_env()

    assert isinstance(state, CloudStorageSyncState)
    assert client.requested_bucket_name == "healthsync-state"
    assert client.bucket_instance.requested_blob_name == "sync.json"
