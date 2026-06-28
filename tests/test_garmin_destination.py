from datetime import datetime, timezone

import pytest

from healthsync.destinations.garmin import (
    GARMIN_TOKENS_FILE_NAME,
    GarminAuthenticationError,
    GarminConfig,
    GarminConfigError,
    GarminUploadError,
    GarminVerificationError,
    GarminWeightDestination,
    build_upload_mapping,
    garmin_record_weight_kg,
    hydrate_session_tokens,
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
        weigh_ins: object | None = None,
        read_error: Exception | None = None,
        calls: list[tuple[str, dict]] | None = None,
        **kwargs,
    ) -> None:
        self.login_error = login_error
        self.upload_error = upload_error
        self.weigh_ins = [] if weigh_ins is None else weigh_ins
        self.read_error = read_error
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

    def get_weigh_ins(self, start_date: str, end_date: str) -> object:
        self.calls.append(
            ("get_weigh_ins", {"start_date": start_date, "end_date": end_date})
        )
        if self.read_error is not None:
            raise self.read_error
        return self.weigh_ins


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
    assert config.verify_uploads is False


def test_config_reads_verification_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GARMIN_VERIFY_UPLOADS", "true")

    config = GarminConfig.from_env()

    assert config.verify_uploads is True


def test_config_reads_tokens_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GARMIN_TOKENS_JSON", '{"oauth1_token": "token"}')

    config = GarminConfig.from_env()

    assert config.tokens_json == '{"oauth1_token": "token"}'


def test_config_rejects_invalid_tokens_json() -> None:
    with pytest.raises(GarminConfigError, match="GARMIN_TOKENS_JSON must be valid JSON"):
        GarminConfig(tokens_json="not-json")


def test_hydrates_session_tokens(tmp_path) -> None:
    tokens_json = '{"oauth1_token": "token"}'

    hydrate_session_tokens(tmp_path / "session", tokens_json)

    assert (tmp_path / "session" / GARMIN_TOKENS_FILE_NAME).read_text(
        encoding="utf-8"
    ) == tokens_json


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


def test_session_tokens_are_written_before_login(tmp_path) -> None:
    calls: list[tuple[str, dict]] = []
    session_dir = tmp_path / "session"

    def factory(**kwargs):
        assert (session_dir / GARMIN_TOKENS_FILE_NAME).exists()
        return FakeGarminClient(calls=calls, **kwargs)

    destination = GarminWeightDestination(
        GarminConfig(
            session_dir=session_dir,
            tokens_json='{"oauth1_token": "token"}',
        ),
        client_factory=factory,
    )

    destination.upload_weight_measurement(make_measurement())

    assert calls[0] == ("login", {"tokenstore": str(session_dir), "kwargs": {}})


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


def test_upload_with_verification_success_reads_back_same_day_weight(tmp_path) -> None:
    calls: list[tuple[str, dict]] = []
    measurement = make_measurement(weight_kg=72.5)

    def factory(**kwargs):
        return FakeGarminClient(
            calls=calls,
            weigh_ins={"dateWeightList": [{"weight": 72500.0}]},
            **kwargs,
        )

    destination = GarminWeightDestination(
        GarminConfig(session_dir=tmp_path / "session", verify_uploads=True),
        client_factory=factory,
    )

    destination.upload_weight_measurement(measurement)

    assert calls == [
        ("login", {"tokenstore": str(tmp_path / "session"), "kwargs": {}}),
        (
            "add_weigh_in",
            {
                "weight": 72.5,
                "unitKey": "kg",
                "timestamp": "2026-06-27T09:30:00+00:00",
            },
        ),
        (
            "get_weigh_ins",
            {"start_date": "2026-06-27", "end_date": "2026-06-27"},
        ),
    ]


def test_garmin_read_back_weight_grams_map_to_kg() -> None:
    assert garmin_record_weight_kg({"weight": 109000.0}) == 109.0
    assert garmin_record_weight_kg({"weightInGrams": 72500}) == 72.5


def test_verification_failure_is_clear_and_not_marked_synced(tmp_path) -> None:
    measurement = make_measurement(weight_kg=72.5)
    state = FileSyncState(tmp_path / "sync_state.json")

    def factory(**kwargs):
        return FakeGarminClient(weigh_ins=[{"weight": 70000.0}], **kwargs)

    destination = GarminWeightDestination(
        GarminConfig(session_dir=tmp_path / "session", verify_uploads=True),
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

    with pytest.raises(GarminVerificationError, match="expected 72.500 kg"):
        destination.upload_weight_measurement(measurement)


def test_verification_disabled_by_default_does_not_read_back(tmp_path) -> None:
    calls: list[tuple[str, dict]] = []

    def factory(**kwargs):
        return FakeGarminClient(
            calls=calls,
            read_error=RuntimeError("read should not happen"),
            **kwargs,
        )

    destination = GarminWeightDestination(
        GarminConfig(session_dir=tmp_path / "session"),
        client_factory=factory,
    )

    destination.upload_weight_measurement(make_measurement())

    assert [name for name, _ in calls] == ["login", "add_weigh_in"]
