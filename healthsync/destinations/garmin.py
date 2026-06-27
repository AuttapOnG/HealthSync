"""Garmin Connect destination adapter for canonical body weight measurements."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Callable

from healthsync.models import WeightMeasurement


DEFAULT_GARMIN_SESSION_DIR = Path(".local/garmin-session")


class GarminDestinationError(RuntimeError):
    """Base class for expected Garmin destination failures."""


class GarminConfigError(GarminDestinationError):
    """Raised when Garmin destination configuration is incomplete or invalid."""


class GarminAuthenticationError(GarminDestinationError):
    """Raised when Garmin authentication cannot be completed."""


class GarminUploadError(GarminDestinationError):
    """Raised when Garmin rejects or fails an upload."""


@dataclass(frozen=True, slots=True)
class GarminConfig:
    """Configuration for Garmin Connect authentication and token storage."""

    email: str | None = None
    password: str | None = None
    session_dir: str | Path = DEFAULT_GARMIN_SESSION_DIR

    @classmethod
    def from_env(cls) -> "GarminConfig":
        """Build Garmin configuration from local environment variables."""

        return cls(
            email=_optional_env("GARMIN_EMAIL"),
            password=_optional_env("GARMIN_PASSWORD"),
            session_dir=os.environ.get("GARMIN_SESSION_DIR", str(DEFAULT_GARMIN_SESSION_DIR)),
        )

    def __post_init__(self) -> None:
        email = _clean_optional(self.email)
        password = _clean_optional(self.password)
        session_dir = Path(self.session_dir)

        if not str(session_dir).strip():
            raise GarminConfigError("GARMIN_SESSION_DIR must not be empty")
        if (email is None) != (password is None):
            raise GarminConfigError(
                "GARMIN_EMAIL and GARMIN_PASSWORD must be provided together"
            )

        object.__setattr__(self, "email", email)
        object.__setattr__(self, "password", password)
        object.__setattr__(self, "session_dir", session_dir)

    @property
    def has_credentials(self) -> bool:
        return self.email is not None and self.password is not None


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
    def from_env(cls) -> "GarminWeightDestination":
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

    def _authenticated_client(self) -> Any:
        if self._client is not None:
            return self._client

        tokenstore = str(self._config.session_dir)

        try:
            client = self._client_factory()
            client.login(tokenstore)
            self._client = client
            return client
        except Exception:
            pass

        if not self._config.has_credentials:
            raise GarminConfigError(
                "Stored Garmin session login failed and GARMIN_EMAIL/GARMIN_PASSWORD "
                "are not configured"
            )

        self._config.session_dir.mkdir(parents=True, exist_ok=True)
        try:
            client = self._client_factory(
                email=self._config.email,
                password=self._config.password,
                prompt_mfa=self._prompt_mfa,
            )
            client.login(tokenstore)
        except Exception as exc:
            raise GarminAuthenticationError(f"Garmin authentication failed: {exc}") from exc

        self._client = client
        return client


def build_upload_mapping(measurement: WeightMeasurement) -> GarminUploadMapping:
    """Map a canonical measurement to the selected Garmin upload call."""

    timestamp = measurement.measured_at.isoformat()
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


def _optional_env(name: str) -> str | None:
    return _clean_optional(os.environ.get(name))


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned or cleaned.startswith("replace-with-"):
        return None
    return cleaned


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
    "GarminAuthenticationError",
    "GarminConfig",
    "GarminConfigError",
    "GarminDestinationError",
    "GarminUploadError",
    "GarminUploadMapping",
    "GarminWeightDestination",
    "build_upload_mapping",
]
