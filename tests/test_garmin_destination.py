from datetime import datetime, timezone

import pytest

from healthsync.destinations.garmin import (
    GarminAuthenticationError,
    GarminConfig,
    GarminConfigError,
    GarminUploadError,
    GarminWeightDestination,
    build_upload_mapping,
)
from healthsync.models import WeightMeasurement
from healthsync.state import FileSyncState
from healthsync.sync_engine import WeightSyncEngine


def make_measurement(
    *,
    weight_kg: float = 72.5,
    body_fat_percent: float | None = None,
    muscle_mass_kg: float | None = None,
) -> WeightMeasurement:
    return WeightMeasurement(
        source="test_source",
        measured_at=datetime(2026, 6, 27, 9, 30, tzinfo=timezone.utc),
        weight_kg=weight_kg,
        body_fat_percent=body_fat_percent,
        muscle_mass_kg=muscle_mass_kg,
    )


class FakeGarminClient:
    def __init__(
        self,
        *,
        login_error: Exception | None = None,
        upload_error: Exception | None = None,
        calls: list[tuple[str, dict]] | None = None,
        **kwargs,
    ) -> None:
        self.login_error = login_error
        self.upload_error = upload_error
        self.calls = calls if calls is not None else []
        self.kwargs = kwargs

    def login(self, tokenstore: str) -> None:
        self.calls.append(("login", {"tokenstore": tokenstore, "kwargs": self.kwargs}))
        if self.login_error is not None:
            raise self.login_error

    def add_weigh_in(self, **kwargs) -> None:
        self.calls.append(("add_weigh_in", kwargs))
        if self.upload_error is not None:
            raise self.upload_error

    def add_body_composition(self, **kwargs) -> None:
        self.calls.append(("add_body_composition", kwargs))
        if self.upload_error is not None:
            raise self.upload_error


class FakeWeightSource:
    def __init__(self, measurements: list[WeightMeasurement]) -> None:
        self.measurements = measurements

    def fetch_weight_measurements(self) -> list[WeightMeasurement]:
        return self.measurements


def test_maps_plain_weight_to_garmin_weigh_in_payload() -> None:
    measurement = make_measurement(weight_kg=72.5)

    mapping = build_upload_mapping(measurement)

    assert mapping.method == "add_weigh_in"
    assert mapping.args == {
        "weight": 72.5,
        "unitKey": "kg",
        "timestamp": "2026-06-27T09:30:00+00:00",
    }


def test_maps_body_fat_to_garmin_body_composition_payload() -> None:
    measurement = make_measurement(
        weight_kg=72.5,
        body_fat_percent=18.2,
        muscle_mass_kg=52.1,
    )

    mapping = build_upload_mapping(measurement)

    assert mapping.method == "add_body_composition"
    assert mapping.args == {
        "timestamp": "2026-06-27T09:30:00+00:00",
        "weight": 72.5,
        "percent_fat": 18.2,
        "muscle_mass": 52.1,
    }


def test_config_reads_environment_and_ignores_placeholders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GARMIN_EMAIL", "replace-with-garmin-email")
    monkeypatch.setenv("GARMIN_PASSWORD", "replace-with-garmin-password")
    monkeypatch.setenv("GARMIN_SESSION_DIR", ".local/test-garmin-session")

    config = GarminConfig.from_env()

    assert config.email is None
    assert config.password is None
    assert str(config.session_dir) == ".local\\test-garmin-session" or str(config.session_dir) == ".local/test-garmin-session"


def test_config_requires_email_and_password_together() -> None:
    with pytest.raises(GarminConfigError, match="provided together"):
        GarminConfig(email="user@example.com", password=None)


def test_missing_credentials_after_session_failure_is_clear(tmp_path) -> None:
    calls: list[tuple[str, dict]] = []

    def factory(**kwargs):
        return FakeGarminClient(login_error=RuntimeError("no saved session"), calls=calls, **kwargs)

    destination = GarminWeightDestination(
        GarminConfig(session_dir=tmp_path / "session"),
        client_factory=factory,
    )

    with pytest.raises(GarminConfigError, match="Stored Garmin session login failed"):
        destination.upload_weight_measurement(make_measurement())


def test_fresh_login_failure_is_clear(tmp_path) -> None:
    def factory(**kwargs):
        return FakeGarminClient(login_error=RuntimeError("bad mfa"), **kwargs)

    destination = GarminWeightDestination(
        GarminConfig(
            email="user@example.com",
            password="secret",
            session_dir=tmp_path / "session",
        ),
        client_factory=factory,
    )

    with pytest.raises(GarminAuthenticationError, match="Garmin authentication failed"):
        destination.upload_weight_measurement(make_measurement())


def test_upload_failure_is_clear_and_not_marked_synced(tmp_path) -> None:
    measurement = make_measurement()
    state = FileSyncState(tmp_path / "sync_state.json")

    def factory(**kwargs):
        if kwargs:
            return FakeGarminClient(
                upload_error=RuntimeError("provider rejected upload"),
                **kwargs,
            )
        return FakeGarminClient(login_error=RuntimeError("no saved session"))

    destination = GarminWeightDestination(
        GarminConfig(
            email="user@example.com",
            password="secret",
            session_dir=tmp_path / "session",
        ),
        client_factory=factory,
    )

    result = WeightSyncEngine(
        FakeWeightSource([measurement]),
        destination,
        sync_state=state,
    ).sync_weight_measurements()

    assert result.uploaded_count == 0
    assert result.failed_count == 1
    assert result.failed_sync_keys == (measurement.sync_key,)
    assert not state.is_synced(measurement.sync_key)

    with pytest.raises(GarminUploadError, match="Garmin weight upload failed"):
        destination.upload_weight_measurement(measurement)
