import json

import pytest

import main
from healthsync.destinations import DryRunWeightDestination, GarminWeightDestination
from healthsync.sync_engine import WeightSyncResult


class FakeRequest:
    def __init__(self, method: str = "POST") -> None:
        self.method = method


def test_sync_weight_http_returns_sync_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "run_weight_sync_from_env",
        lambda: WeightSyncResult(
            fetched_count=2,
            uploaded_count=1,
            failed_count=0,
            skipped_count=1,
            skipped_sync_keys=("already-synced",),
        ),
    )

    body, status, headers = main.sync_weight_http(FakeRequest())

    assert status == 200
    assert headers == {"Content-Type": "application/json"}
    assert json.loads(body) == {
        "failed_count": 0,
        "failed_sync_keys": [],
        "fetched_count": 2,
        "keepalive_count": 0,
        "keepalive_failed": False,
        "destination_suspended": False,
        "destination_suspension_reason": None,
        "skipped_count": 1,
        "skipped_sync_keys": ["already-synced"],
        "uploaded_count": 1,
    }


def test_sync_weight_http_logs_sync_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        main,
        "run_weight_sync_from_env",
        lambda: WeightSyncResult(
            fetched_count=1,
            uploaded_count=0,
            failed_count=0,
            skipped_count=1,
            skipped_sync_keys=("already-synced",),
        ),
    )

    main.sync_weight_http(FakeRequest())

    record = json.loads(capsys.readouterr().out)
    assert record["message"] == "HealthSync weight sync result"
    assert record["severity"] == "INFO"
    assert record["http_status"] == 200
    assert record["fetched_count"] == 1
    assert record["uploaded_count"] == 0
    assert record["failed_count"] == 0
    assert record["skipped_count"] == 1
    assert record["keepalive_count"] == 0
    assert record["keepalive_failed"] is False
    assert record["destination_suspended"] is False
    assert record["destination_suspension_reason"] is None
    assert record["skipped_sync_keys"] == ["already-synced"]


def test_sync_weight_http_reports_keepalive_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main,
        "run_weight_sync_from_env",
        lambda: WeightSyncResult(
            fetched_count=1,
            uploaded_count=0,
            failed_count=0,
            skipped_count=1,
            keepalive_failed=True,
            skipped_sync_keys=("already-synced",),
        ),
    )

    body, status, _headers = main.sync_weight_http(FakeRequest())

    assert status == 502
    assert json.loads(body)["keepalive_failed"] is True


def test_sync_weight_http_reports_sync_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail() -> WeightSyncResult:
        raise RuntimeError("Zepp Life API request failed")

    monkeypatch.setattr(main, "run_weight_sync_from_env", fail)

    body, status, _headers = main.sync_weight_http(FakeRequest())

    assert status == 500
    assert json.loads(body) == {"error": "Zepp Life API request failed"}


def test_sync_weight_http_rejects_unsupported_methods() -> None:
    body, status, _headers = main.sync_weight_http(FakeRequest("PUT"))

    assert status == 405
    assert json.loads(body) == {"error": "Method not allowed"}


def test_cloud_destination_defaults_to_dry_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HEALTHSYNC_DESTINATION", raising=False)

    destination = main.build_destination_from_env("dry-run")

    assert isinstance(destination, DryRunWeightDestination)


def test_cloud_destination_requires_real_upload_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HEALTHSYNC_ALLOW_REAL_UPLOAD", raising=False)

    with pytest.raises(ValueError, match="Refusing Garmin upload"):
        main.build_destination_from_env("garmin")


def test_cloud_destination_builds_garmin_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HEALTHSYNC_ALLOW_REAL_UPLOAD", "true")
    monkeypatch.setenv("GARMIN_EMAIL", "replace-with-garmin-email")
    monkeypatch.setenv("GARMIN_PASSWORD", "replace-with-garmin-password")
    monkeypatch.setenv("GARMIN_SESSION_DIR", ".local/test-garmin-session")

    destination = main.build_destination_from_env("garmin")

    assert isinstance(destination, GarminWeightDestination)


def test_cloud_sync_state_is_disabled_for_dry_run() -> None:
    assert main.build_cloud_sync_state("dry-run") is None

