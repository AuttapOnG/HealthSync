"""Garmin Connect destination adapter for canonical body weight measurements."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from healthsync.models import WeightMeasurement

DEFAULT_GARMIN_SESSION_DIR = Path(".local/garmin-session")
GARMIN_TOKENS_JSON_ENV_VAR = "GARMIN_TOKENS_JSON"
GARMIN_TOKENS_FILE_NAME = "garmin_tokens.json"
GARMIN_TOKENS_SECRET_ID_ENV_VAR = "GARMIN_TOKENS_SECRET_ID"
GARMIN_TOKENS_SECRET_PROJECT_ENV_VAR = "GARMIN_TOKENS_SECRET_PROJECT"
GARMIN_VERIFY_UPLOADS_ENV_VAR = "GARMIN_VERIFY_UPLOADS"
WEIGHT_MATCH_TOLERANCE_KG = 0.01
LOGGER = logging.getLogger(__name__)


class GarminDestinationError(RuntimeError):
    """Base class for expected Garmin destination failures."""


class GarminConfigError(GarminDestinationError):
    """Raised when Garmin destination configuration is incomplete or invalid."""


class GarminAuthenticationError(GarminDestinationError):
    """Raised when Garmin authentication cannot be completed."""


class GarminUploadError(GarminDestinationError):
    """Raised when Garmin rejects or fails an upload."""


class GarminVerificationError(GarminDestinationError):
    """Raised when Garmin upload read-back verification fails."""


@dataclass(frozen=True, slots=True)
class GarminConfig:
    """Configuration for Garmin Connect authentication and token storage."""

    email: str | None = None
    password: str | None = None
    session_dir: str | Path = DEFAULT_GARMIN_SESSION_DIR
    tokens_json: str | None = None
    tokens_secret_id: str | None = None
    tokens_secret_project: str | None = None
    verify_uploads: bool = False

    @classmethod
    def from_env(cls) -> GarminConfig:
        """Build Garmin configuration from local environment variables."""

        return cls(
            email=_optional_env("GARMIN_EMAIL"),
            password=_optional_env("GARMIN_PASSWORD"),
            session_dir=os.environ.get(
                "GARMIN_SESSION_DIR", str(DEFAULT_GARMIN_SESSION_DIR)
            ),
            tokens_json=_optional_env(GARMIN_TOKENS_JSON_ENV_VAR),
            tokens_secret_id=_optional_env(GARMIN_TOKENS_SECRET_ID_ENV_VAR),
            tokens_secret_project=_optional_env(GARMIN_TOKENS_SECRET_PROJECT_ENV_VAR),
            verify_uploads=_optional_bool_env(
                GARMIN_VERIFY_UPLOADS_ENV_VAR, default=False
            ),
        )

    def __post_init__(self) -> None:
        email = _clean_optional(self.email)
        password = _clean_optional(self.password)
        tokens_json = _clean_optional(self.tokens_json)
        tokens_secret_id = _clean_optional(self.tokens_secret_id)
        tokens_secret_project = _clean_optional(self.tokens_secret_project)
        session_dir = Path(self.session_dir)

        if not str(session_dir).strip():
            raise GarminConfigError("GARMIN_SESSION_DIR must not be empty")
        if (email is None) != (password is None):
            raise GarminConfigError(
                "GARMIN_EMAIL and GARMIN_PASSWORD must be provided together"
            )
        if not isinstance(self.verify_uploads, bool):
            raise GarminConfigError("verify_uploads must be a bool")
        if tokens_json is not None:
            _validate_tokens_json(tokens_json)
        if tokens_secret_project is not None and tokens_secret_id is None:
            raise GarminConfigError(
                f"{GARMIN_TOKENS_SECRET_PROJECT_ENV_VAR} requires "
                f"{GARMIN_TOKENS_SECRET_ID_ENV_VAR}"
            )

        object.__setattr__(self, "email", email)
        object.__setattr__(self, "password", password)
        object.__setattr__(self, "session_dir", session_dir)
        object.__setattr__(self, "tokens_json", tokens_json)
        object.__setattr__(self, "tokens_secret_id", tokens_secret_id)
        object.__setattr__(self, "tokens_secret_project", tokens_secret_project)

    @property
    def has_credentials(self) -> bool:
        return self.email is not None and self.password is not None

    @property
    def session_dir_path(self) -> Path:
        """Return ``session_dir`` as a ``Path``.

        ``session_dir`` is declared as ``str | Path`` to accept environment
        strings at construction time, but ``__post_init__`` always
        normalizes it to a ``Path`` before this property (or any other
        code) can observe it.
        """

        return cast(Path, self.session_dir)


@dataclass(frozen=True, slots=True)
class GarminUploadMapping:
    """Provider-specific Garmin upload method and arguments."""

    method: str
    args: dict[str, Any]


ClientFactory = Callable[..., Any]
MfaPrompt = Callable[[], str]


class GarminWeightDestination:
    """Upload canonical weight measurements to Garmin Connect."""

    def __init__(
        self,
        config: GarminConfig | None = None,
        *,
        client_factory: ClientFactory | None = None,
        prompt_mfa: MfaPrompt | None = None,
    ) -> None:
        self._config = config or GarminConfig.from_env()
        self._client_factory = client_factory or _default_client_factory
        self._prompt_mfa = prompt_mfa or _prompt_mfa
        self._client: Any | None = None

    @classmethod
    def from_env(cls) -> GarminWeightDestination:
        """Create a Garmin destination using GARMIN_* environment variables."""

        return cls(GarminConfig.from_env())

    def upload_weight_measurement(self, measurement: WeightMeasurement) -> None:
        """Upload one canonical weight measurement to Garmin Connect."""

        client = self._authenticated_client()
        mapping = build_upload_mapping(measurement)
        upload_method = getattr(client, mapping.method)

        try:
            upload_method(**mapping.args)
        except Exception as exc:
            raise GarminUploadError(f"Garmin weight upload failed: {exc}") from exc

        if self._config.verify_uploads:
            verify_uploaded_weight(client, measurement)

    def keepalive(self) -> None:
        """Make one read-only Garmin request so cached tokens can refresh."""

        client = self._authenticated_client()
        try:
            if hasattr(client, "get_user_profile"):
                client.get_user_profile()
            else:
                read_weight_records_for_date(client, date.today())
        except Exception as exc:
            raise GarminAuthenticationError(f"Garmin keepalive failed: {exc}") from exc
        persist_session_tokens(self._config)

    def _authenticated_client(self) -> Any:
        if self._client is not None:
            return self._client

        tokenstore = str(self._config.session_dir)
        hydrate_session_tokens(self._config.session_dir_path, self._config.tokens_json)

        try:
            client = self._client_factory()
            client.login(tokenstore)
            persist_session_tokens(self._config)
            self._client = client
            return client
        except Exception as exc:
            stored_session_error = exc
            LOGGER.warning("Stored Garmin session login failed: %s", stored_session_error)

        if not self._config.has_credentials:
            raise GarminConfigError(
                "Stored Garmin session login failed and GARMIN_EMAIL/GARMIN_PASSWORD "
                "are not configured"
            ) from stored_session_error

        self._config.session_dir_path.mkdir(parents=True, exist_ok=True)
        try:
            client = self._client_factory(
                email=self._config.email,
                password=self._config.password,
                prompt_mfa=self._prompt_mfa,
            )
            client.login(tokenstore)
        except Exception as exc:
            raise GarminAuthenticationError(
                f"Garmin authentication failed: {exc}"
            ) from exc

        persist_session_tokens(self._config)
        self._client = client
        return client


def hydrate_session_tokens(session_dir: Path, tokens_json: str | None) -> None:
    """Write a configured Garmin token cache into the session directory."""

    if tokens_json is None:
        return

    session_dir.mkdir(parents=True, exist_ok=True)
    token_path = session_dir / GARMIN_TOKENS_FILE_NAME
    if token_path.exists():
        return
    token_path.write_text(tokens_json, encoding="utf-8")


def persist_session_tokens(config: GarminConfig) -> None:
    """Persist a refreshed Garmin token cache to Secret Manager when configured."""

    if config.tokens_secret_id is None:
        return

    token_path = config.session_dir_path / GARMIN_TOKENS_FILE_NAME
    try:
        tokens_json = token_path.read_text(encoding="utf-8")
        _validate_tokens_json(tokens_json)
        persist_tokens_json_to_secret_manager(
            tokens_json,
            secret_id=config.tokens_secret_id,
            project_id=config.tokens_secret_project,
        )
    except Exception as exc:
        LOGGER.warning("Failed to persist refreshed Garmin session tokens: %s", exc)


def persist_tokens_json_to_secret_manager(
    tokens_json: str,
    *,
    secret_id: str,
    project_id: str | None = None,
) -> None:
    """Add a new Secret Manager version when Garmin token JSON changed."""

    _validate_tokens_json(tokens_json)

    try:
        from google.api_core.exceptions import NotFound
        from google.auth import default as google_auth_default
        from google.cloud import secretmanager
    except ImportError as exc:
        raise GarminConfigError(
            "google-cloud-secret-manager is not installed; install runtime dependencies"
        ) from exc

    resolved_project_id = project_id
    if resolved_project_id is None:
        _credentials, resolved_project_id = google_auth_default()
    if resolved_project_id is None:
        raise GarminConfigError(
            f"{GARMIN_TOKENS_SECRET_PROJECT_ENV_VAR} is required when the Google "
            "Cloud project cannot be inferred"
        )

    client = secretmanager.SecretManagerServiceClient()
    secret_name = f"projects/{resolved_project_id}/secrets/{secret_id}"
    latest_name = f"{secret_name}/versions/latest"

    try:
        latest = client.access_secret_version(request={"name": latest_name})
        latest_tokens_json = latest.payload.data.decode("utf-8")
        if latest_tokens_json == tokens_json:
            return
    except NotFound:
        pass

    client.add_secret_version(
        request={
            "parent": secret_name,
            "payload": {"data": tokens_json.encode("utf-8")},
        }
    )


def build_upload_mapping(measurement: WeightMeasurement) -> GarminUploadMapping:
    """Map a canonical measurement to the selected Garmin upload call."""

    timestamp = _garmin_timestamp(measurement.measured_at)
    if measurement.body_fat_percent is not None or measurement.muscle_mass_kg is not None:
        args: dict[str, Any] = {
            "timestamp": timestamp,
            "weight": measurement.weight_kg,
        }
        if measurement.body_fat_percent is not None:
            args["percent_fat"] = measurement.body_fat_percent
        if measurement.muscle_mass_kg is not None:
            args["muscle_mass"] = measurement.muscle_mass_kg
        return GarminUploadMapping(method="add_body_composition", args=args)

    return GarminUploadMapping(
        method="add_weigh_in",
        args={
            "weight": measurement.weight_kg,
            "unitKey": "kg",
            "timestamp": timestamp,
        },
    )


def _garmin_timestamp(value: datetime) -> str:
    """Render a measurement time as naive UTC, the format Garmin expects."""

    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value.isoformat()


def verify_uploaded_weight(client: Any, measurement: WeightMeasurement) -> None:
    """Read back Garmin weights for the measurement date and confirm a match."""

    measurement_date = measurement.measured_at.date()
    try:
        records = read_weight_records_for_date(client, measurement_date)
    except GarminVerificationError:
        raise
    except Exception as exc:
        raise GarminVerificationError(
            "Garmin weight verification read failed for "
            f"{measurement_date.isoformat()}: {exc}"
        ) from exc

    read_back_weights = [
        weight_kg
        for record in _iter_weight_record_dicts(records)
        if (weight_kg := garmin_record_weight_kg(record)) is not None
    ]
    for weight_kg in read_back_weights:
        if abs(weight_kg - measurement.weight_kg) <= WEIGHT_MATCH_TOLERANCE_KG:
            return

    values = ", ".join(f"{weight_kg:.3f} kg" for weight_kg in read_back_weights)
    if not values:
        values = "no Garmin weight records"
    raise GarminVerificationError(
        "Garmin weight verification failed: expected "
        f"{measurement.weight_kg:.3f} kg on {measurement_date.isoformat()}, "
        f"read back {values}"
    )


def read_weight_records_for_date(client: Any, measurement_date: date) -> Any:
    """Read Garmin weight records for one date using the selected client API."""

    if not hasattr(client, "get_weigh_ins"):
        raise GarminVerificationError(
            "Garmin weight verification requires client.get_weigh_ins"
        )

    date_value = measurement_date.isoformat()
    return client.get_weigh_ins(date_value, date_value)


def garmin_record_weight_kg(record: dict[str, Any]) -> float | None:
    """Return Garmin read-back weight in kg; Garmin read APIs report grams."""

    value = record.get("weight")
    if value is None:
        value = record.get("weightInGrams")
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) / 1000


def _iter_weight_record_dicts(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        dict_records: list[dict[str, Any]] = (
            [value] if "weight" in value or "weightInGrams" in value else []
        )
        for child in value.values():
            dict_records.extend(_iter_weight_record_dicts(child))
        return dict_records
    if isinstance(value, list):
        records: list[dict[str, Any]] = []
        for child in value:
            records.extend(_iter_weight_record_dicts(child))
        return records
    return []


def _optional_env(name: str) -> str | None:
    return _clean_optional(os.environ.get(name))


def _optional_bool_env(name: str, *, default: bool) -> bool:
    value = _clean_optional(os.environ.get(name))
    if value is None:
        return default
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise GarminConfigError(f"{name} must be one of true/false, yes/no, on/off, or 1/0")


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().removeprefix("\ufeff")
    if not cleaned or cleaned.startswith("replace-with-"):
        return None
    return cleaned


def _validate_tokens_json(value: str) -> None:
    try:
        raw = json.loads(value)
    except json.JSONDecodeError as exc:
        raise GarminConfigError(
            f"{GARMIN_TOKENS_JSON_ENV_VAR} must be valid JSON"
        ) from exc

    if not isinstance(raw, dict):
        raise GarminConfigError(f"{GARMIN_TOKENS_JSON_ENV_VAR} must be a JSON object")


def _default_client_factory(**kwargs: Any) -> Any:
    try:
        from garminconnect import Garmin
    except ImportError as exc:
        raise GarminConfigError(
            "garminconnect is not installed; install project POC/runtime dependencies"
        ) from exc

    return Garmin(**kwargs)


def _prompt_mfa() -> str:
    return input("Garmin MFA/2FA code: ").strip()


__all__ = [
    "DEFAULT_GARMIN_SESSION_DIR",
    "GARMIN_TOKENS_FILE_NAME",
    "GARMIN_TOKENS_JSON_ENV_VAR",
    "GARMIN_TOKENS_SECRET_ID_ENV_VAR",
    "GARMIN_TOKENS_SECRET_PROJECT_ENV_VAR",
    "GarminAuthenticationError",
    "GarminConfig",
    "GarminConfigError",
    "GarminDestinationError",
    "GarminUploadError",
    "GarminUploadMapping",
    "GarminVerificationError",
    "GarminWeightDestination",
    "build_upload_mapping",
    "garmin_record_weight_kg",
    "hydrate_session_tokens",
    "persist_session_tokens",
    "persist_tokens_json_to_secret_manager",
    "read_weight_records_for_date",
    "verify_uploaded_weight",
]
