import pytest

from healthsync.destinations import DryRunWeightDestination, GarminWeightDestination
from scripts.sync_weight import build_destination, real_upload_allowed


def test_runner_defaults_to_dry_run_destination() -> None:
    destination = build_destination("dry-run", allow_real_upload_flag=False)

    assert isinstance(destination, DryRunWeightDestination)


def test_garmin_destination_requires_env_and_command_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HEALTHSYNC_ALLOW_REAL_UPLOAD", raising=False)

    with pytest.raises(ValueError, match="Refusing Garmin upload"):
        build_destination("garmin", allow_real_upload_flag=True)

    monkeypatch.setenv("HEALTHSYNC_ALLOW_REAL_UPLOAD", "true")
    with pytest.raises(ValueError, match="Refusing Garmin upload"):
        build_destination("garmin", allow_real_upload_flag=False)


def test_garmin_destination_builds_only_when_double_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HEALTHSYNC_ALLOW_REAL_UPLOAD", "true")
    monkeypatch.setenv("GARMIN_EMAIL", "replace-with-garmin-email")
    monkeypatch.setenv("GARMIN_PASSWORD", "replace-with-garmin-password")
    monkeypatch.setenv("GARMIN_SESSION_DIR", ".local/test-garmin-session")

    destination = build_destination("garmin", allow_real_upload_flag=True)

    assert isinstance(destination, GarminWeightDestination)


@pytest.mark.parametrize(
    ("env_value", "flag", "expected"),
    [
        ("true", True, True),
        ("TRUE", True, True),
        ("false", True, False),
        ("true", False, False),
    ],
)
def test_real_upload_allowed_requires_true_env_and_flag(
    monkeypatch: pytest.MonkeyPatch,
    env_value: str,
    flag: bool,
    expected: bool,
) -> None:
    monkeypatch.setenv("HEALTHSYNC_ALLOW_REAL_UPLOAD", env_value)

    assert real_upload_allowed(flag) is expected


def test_real_upload_allowed_is_false_when_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HEALTHSYNC_ALLOW_REAL_UPLOAD", raising=False)

    assert not real_upload_allowed(True)
