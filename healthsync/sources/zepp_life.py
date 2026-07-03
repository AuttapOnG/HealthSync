"""Zepp Life source adapter for body weight measurements."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from healthsync.models import WeightMeasurement


class ZeppLifeSourceError(RuntimeError):
    """Raised when Zepp Life data cannot be fetched or parsed safely."""


@dataclass(frozen=True, slots=True)
class ZeppLifeConfig:
    """Configuration for a user-owned Zepp Life app session."""

    host: str
    user_id: str
    app_token: str
    days: int = 30
    use_profile_fallback: bool = True

    @classmethod
    def from_env(cls) -> "ZeppLifeConfig":
        """Build configuration from local environment variables."""

        days_value = os.environ.get("ZEPP_DAYS", "30").strip()
        try:
            days = int(days_value)
        except ValueError as exc:
            raise ZeppLifeSourceError("ZEPP_DAYS must be an integer") from exc

        return cls(
            host=_require_env("ZEPP_HOST"),
            user_id=_require_env("ZEPP_USER_ID"),
            app_token=_require_env("ZEPP_APP_TOKEN"),
            days=days,
        )

    def __post_init__(self) -> None:
        host = self.host.strip().removeprefix("https://").removeprefix("http://").strip("/")
        user_id = self.user_id.strip()
        app_token = self.app_token.strip()

        if not host:
            raise ZeppLifeSourceError("Zepp Life host is required")
        if not user_id:
            raise ZeppLifeSourceError("Zepp Life user_id is required")
        if not app_token:
            raise ZeppLifeSourceError("Zepp Life app_token is required")
        if self.days <= 0:
            raise ZeppLifeSourceError("Zepp Life days must be positive")

        object.__setattr__(self, "host", host)
        object.__setattr__(self, "user_id", user_id)
        object.__setattr__(self, "app_token", app_token)


HttpGet = Callable[[str, dict[str, str]], Any]


class ZeppLifeWeightSource:
    """Fetch weight measurements from Zepp Life's user-owned app session API."""

    source_name = "zepp_life_api"

    def __init__(
        self,
        config: ZeppLifeConfig | None = None,
        *,
        http_get: HttpGet | None = None,
    ) -> None:
        self._config = config or ZeppLifeConfig.from_env()
        self._http_get = http_get or _fetch_json

    @classmethod
    def from_env(cls) -> "ZeppLifeWeightSource":
        """Create a source adapter using ZEPP_* environment variables."""

        return cls(ZeppLifeConfig.from_env())

    def fetch_weight_measurements(self) -> list[WeightMeasurement]:
        """Return canonical weight measurements from Zepp Life."""

        records_payload = self._http_get(self._weight_records_url(), self._headers())
        records = _iter_record_dicts(records_payload)

        if records:
            return _parse_measurements(records, endpoint="weightRecords", fallback=False)

        if not self._config.use_profile_fallback:
            return []

        profile_payload = self._http_get(self._profile_url(), self._headers())
        profile_records = _iter_record_dicts(profile_payload)
        if not profile_records:
            return []

        return _parse_measurements(profile_records, endpoint="profile", fallback=True)

    def _headers(self) -> dict[str, str]:
        return {
            "Apptoken": self._config.app_token,
            "Appname": "com.huami.webapp",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://user.huami.com",
            "Referer": "https://user.huami.com/",
            "User-Agent": "HealthSync/0.1",
        }

    def _weight_records_url(self) -> str:
        user_id = quote(self._config.user_id, safe="")
        return (
            f"https://{self._config.host}/users/{user_id}/members/-1/"
            f"weightRecords?days={self._config.days}"
        )

    def _profile_url(self) -> str:
        user_id = quote(self._config.user_id, safe="")
        return f"https://{self._config.host}/users/{user_id}"


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ZeppLifeSourceError(f"Missing required environment variable: {name}")
    return value


def _fetch_json(url: str, headers: dict[str, str]) -> Any:
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ZeppLifeSourceError(f"Zepp Life API returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise ZeppLifeSourceError(f"Zepp Life API request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ZeppLifeSourceError("Zepp Life API returned invalid JSON") from exc


def _iter_record_dicts(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        raise ZeppLifeSourceError("Zepp Life response must be a JSON object or list")

    for key in ("items", "data", "records", "weightRecords", "weight_records"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _iter_record_dicts(value)
            if nested:
                return nested

    if _looks_like_weight_record(payload):
        return [payload]
    return []


def _looks_like_weight_record(record: dict[str, Any]) -> bool:
    return _first_float(record, ("weight", "weightKg", "weight_kg", "value")) is not None


def _parse_measurements(
    records: list[dict[str, Any]],
    *,
    endpoint: str,
    fallback: bool,
) -> list[WeightMeasurement]:
    measurements: list[WeightMeasurement] = []
    invalid_count = 0

    for record in records:
        parsed = _parse_record(record, endpoint=endpoint, fallback=fallback)
        if parsed is None:
            invalid_count += 1
            continue
        measurements.append(parsed)

    if not measurements and invalid_count:
        raise ZeppLifeSourceError("No parseable Zepp Life weight records found")

    return measurements


def _parse_record(
    record: dict[str, Any],
    *,
    endpoint: str,
    fallback: bool,
) -> WeightMeasurement | None:
    measured_at = _first_datetime(
        record,
        (
            "date",
            "time",
            "timestamp",
            "datetime",
            "measuredAt",
            "measureTime",
            "createdTime",
            "generatedTime",
            "lastUpdateTime",
        ),
    )
    weight_kg = _first_float(record, ("weight", "weightKg", "weight_kg", "value"))
    if measured_at is None or weight_kg is None:
        return None

    return WeightMeasurement(
        source=ZeppLifeWeightSource.source_name,
        measured_at=measured_at,
        weight_kg=weight_kg,
        body_fat_percent=_first_float(
            record,
            ("fat", "bodyFat", "body_fat", "bodyFatRate", "body_fat_percent"),
        ),
        muscle_mass_kg=_first_float(
            record,
            ("muscle", "muscleMass", "muscle_mass", "muscle_mass_kg"),
        ),
        metadata={
            "provider": "zepp_life",
            "endpoint": endpoint,
            "profile_fallback": fallback,
            "raw_keys": sorted(record.keys()),
        },
    )


def _first_datetime(record: dict[str, Any], keys: tuple[str, ...]) -> datetime | None:
    for key in keys:
        parsed = _parse_datetime(record.get(key))
        if parsed is not None:
            return parsed
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)

    cleaned = str(value).strip()
    if not cleaned:
        return None

    for date_format in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(cleaned, date_format)
        except ValueError:
            pass

    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        return None


def _first_float(record: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


__all__ = ["ZeppLifeConfig", "ZeppLifeSourceError", "ZeppLifeWeightSource"]
