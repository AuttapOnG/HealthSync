from datetime import datetime, timedelta, timezone
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


class KeepaliveWeightDestination(RecordingWeightDestination):
    def __init__(self, *, fail_keepalive: bool = False) -> None:
        super().__init__()
        self.keepalive_count = 0
        self.fail_keepalive = fail_keepalive

    def keepalive(self) -> None:
        self.keepalive_count += 1
        if self.fail_keepalive:
            raise RuntimeError("provider auth failed")


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
    assert result.keepalive_count == 0
    assert result.keepalive_failed is False
    assert result.skipped_sync_keys == (measurement.sync_key,)


def test_sync_engine_keeps_destination_alive_when_everything_is_skipped(
    tmp_path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    measurement = make_measurement()
    state = FileSyncState(tmp_path / "sync_state.json")
    state.mark_synced(measurement.sync_key)
    destination = KeepaliveWeightDestination()

    with caplog.at_level("INFO", logger="healthsync.sync_engine"):
        result = WeightSyncEngine(
            FakeWeightSource([measurement]),
            destination,
            sync_state=state,
        ).sync_weight_measurements()

    assert destination.uploaded == []
    assert destination.keepalive_count == 1
    assert result.uploaded_count == 0
    assert result.skipped_count == 1
    assert result.keepalive_count == 1
    assert result.keepalive_failed is False
    assert "Keeping destination session alive after duplicate-only sync" in caplog.text
    assert "Destination keepalive succeeded" in caplog.text


def test_sync_engine_reports_keepalive_failure_without_marking_upload_failed(
    tmp_path,
) -> None:
    measurement = make_measurement()
    state = FileSyncState(tmp_path / "sync_state.json")
    state.mark_synced(measurement.sync_key)
    destination = KeepaliveWeightDestination(fail_keepalive=True)

    result = WeightSyncEngine(
        FakeWeightSource([measurement]),
        destination,
        sync_state=state,
    ).sync_weight_measurements()

    assert destination.keepalive_count == 1
    assert result.failed_count == 0
    assert result.keepalive_count == 0
    assert result.keepalive_failed is True
    assert state.get_destination_suspension("garmin") is None


def test_sync_engine_marks_destination_suspended_after_keepalive_failure(
    tmp_path,
) -> None:
    measurement = make_measurement()
    state = FileSyncState(tmp_path / "sync_state.json")
    state.mark_synced(measurement.sync_key)
    destination = KeepaliveWeightDestination(fail_keepalive=True)

    result = WeightSyncEngine(
        FakeWeightSource([measurement]),
        destination,
        sync_state=state,
        destination_name="garmin",
    ).sync_weight_measurements()

    suspension = state.get_destination_suspension("garmin")
    assert result.keepalive_failed is True
    assert suspension is not None
    assert suspension.manual is True
    assert suspension.reason == "keepalive failed"


def test_sync_engine_skips_provider_calls_when_destination_suspended(tmp_path) -> None:
    measurement = make_measurement()
    state = FileSyncState(tmp_path / "sync_state.json")
    state.mark_destination_suspended("garmin", reason="previous 429")
    destination = KeepaliveWeightDestination()

    result = WeightSyncEngine(
        FakeWeightSource([measurement]),
        destination,
        sync_state=state,
        destination_name="garmin",
    ).sync_weight_measurements()

    assert destination.uploaded == []
    assert destination.keepalive_count == 0
    assert result.fetched_count == 0
    assert result.uploaded_count == 0
    assert result.destination_suspended is True
    assert result.destination_suspension_reason == "previous 429"


def test_sync_engine_does_not_keepalive_after_real_upload(tmp_path) -> None:
    measurement = make_measurement()
    state = FileSyncState(tmp_path / "sync_state.json")
    destination = KeepaliveWeightDestination()

    result = WeightSyncEngine(
        FakeWeightSource([measurement]),
        destination,
        sync_state=state,
    ).sync_weight_measurements()

    assert destination.uploaded == [measurement]
    assert destination.keepalive_count == 0
    assert result.uploaded_count == 1
    assert result.keepalive_count == 0
    assert result.keepalive_failed is False


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


def test_sync_engine_stops_uploading_after_first_upload_failure(tmp_path) -> None:
    measurements = [make_measurement(70.0), make_measurement(71.0)]
    state = FileSyncState(tmp_path / "sync_state.json")
    destination = FailingDestination()

    result = WeightSyncEngine(
        FakeWeightSource(measurements),
        destination,
        sync_state=state,
        destination_name="garmin",
    ).sync_weight_measurements()

    assert destination.seen == [measurements[0]]
    assert result.fetched_count == 2
    assert result.uploaded_count == 0
    assert result.failed_count == 1
    assert result.failed_sync_keys == (measurements[0].sync_key,)


def test_sync_engine_marks_destination_suspended_after_upload_failure(tmp_path) -> None:
    measurement = make_measurement()
    state = FileSyncState(tmp_path / "sync_state.json")
    destination = FailingDestination()

    result = WeightSyncEngine(
        FakeWeightSource([measurement]),
        destination,
        sync_state=state,
        destination_name="garmin",
    ).sync_weight_measurements()

    suspension = state.get_destination_suspension("garmin")
    assert result.failed_count == 1
    assert suspension is not None
    assert suspension.manual is True
    assert suspension.reason == "upload failed"


def test_file_sync_state_loads_and_saves_state(tmp_path) -> None:
    measurement = make_measurement()
    state_path = tmp_path / "nested" / "sync_state.json"

    FileSyncState(state_path).mark_synced(measurement.sync_key)
    reloaded = FileSyncState(state_path)

    assert reloaded.is_synced(measurement.sync_key)
    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "synced_weight_keys": [measurement.sync_key]
    }


def test_file_sync_state_saves_manual_destination_suspension(tmp_path) -> None:
    state_path = tmp_path / "sync_state.json"
    state = FileSyncState(state_path)

    state.mark_destination_suspended("Garmin", reason="previous 429")
    reloaded = FileSyncState(state_path)
    suspension = reloaded.get_destination_suspension("garmin")

    assert suspension is not None
    assert suspension.manual is True
    assert suspension.suspended_until is None
    assert suspension.reason == "previous 429"
    assert json.loads(state_path.read_text(encoding="utf-8"))[
        "destination_suspensions"
    ] == {
        "garmin": {
            "manual": True,
            "reason": "previous 429",
        }
    }


def test_file_sync_state_expiring_destination_suspension(tmp_path) -> None:
    state = FileSyncState(tmp_path / "sync_state.json")
    now = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)

    state.mark_destination_suspended(
        "garmin",
        until=now + timedelta(hours=1),
        reason="temporary",
    )

    assert state.get_destination_suspension("garmin", now=now) is not None
    assert (
        state.get_destination_suspension(
            "garmin",
            now=now + timedelta(hours=2),
        )
        is None
    )


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
    def __init__(self, text: str | None = None, *, generation: int | None = None) -> None:
        self.text = text
        self.generation = generation if generation is not None else (
            1 if text is not None else None
        )
        self.uploaded_text: str | None = None
        self.content_type: str | None = None
        self.upload_error: Exception | None = None
        self.if_generation_matches: list[int | None] = []

    def exists(self) -> bool:
        return self.text is not None

    def reload(self) -> None:
        pass

    def download_as_text(self, encoding: str = "utf-8") -> str:
        return self.text or ""

    def upload_from_string(
        self,
        text: str,
        *,
        content_type: str,
        if_generation_match: int | None = None,
    ) -> None:
        self.if_generation_matches.append(if_generation_match)
        if self.upload_error is not None:
            raise self.upload_error
        self.text = text
        self.uploaded_text = text
        self.content_type = content_type
        self.generation = (self.generation or 0) + 1


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


def test_cloud_storage_sync_state_saves_with_generation_precondition() -> None:
    blob = FakeStorageBlob(json.dumps({"synced_weight_keys": []}), generation=5)
    state = CloudStorageSyncState(
        "test-bucket",
        "state/sync.json",
        client=FakeStorageClient(blob),
    )

    state.mark_synced("key-1")
    state.mark_synced("key-2")

    assert blob.if_generation_matches == [5, 6]


def test_cloud_storage_sync_state_requires_missing_blob_for_first_save() -> None:
    blob = FakeStorageBlob()
    state = CloudStorageSyncState(
        "test-bucket",
        "state/sync.json",
        client=FakeStorageClient(blob),
    )

    state.mark_synced("key-1")

    assert blob.if_generation_matches == [0]


def test_cloud_storage_sync_state_save_conflict_is_clear() -> None:
    class PreconditionFailed(Exception):
        pass

    blob = FakeStorageBlob(json.dumps({"synced_weight_keys": []}), generation=5)
    blob.upload_error = PreconditionFailed("412 precondition failed")
    state = CloudStorageSyncState(
        "test-bucket",
        "state/sync.json",
        client=FakeStorageClient(blob),
    )

    with pytest.raises(RuntimeError, match="modified by another run"):
        state.mark_synced("key-1")


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
