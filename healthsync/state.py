"""Sync state backends for duplicate prevention."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


DEFAULT_SYNC_STATE_PATH = Path("data/sync_state.json")
SYNC_STATE_ENV_VAR = "HEALTHSYNC_SYNC_STATE_PATH"
SYNC_STATE_BACKEND_ENV_VAR = "HEALTHSYNC_STATE_BACKEND"
GCS_SYNC_STATE_BUCKET_ENV_VAR = "HEALTHSYNC_GCS_STATE_BUCKET"
GCS_SYNC_STATE_BLOB_ENV_VAR = "HEALTHSYNC_GCS_STATE_BLOB"
DEFAULT_GCS_SYNC_STATE_BLOB = "healthsync/sync_state.json"


@runtime_checkable
class SyncState(Protocol):
    """State backend that tracks successfully synced measurement keys."""

    def is_synced(self, sync_key: str) -> bool:
        """Return whether a sync key has already been uploaded successfully."""

    def mark_synced(self, sync_key: str) -> None:
        """Persist a sync key after a successful upload."""


@dataclass(frozen=True, slots=True)
class DestinationSuspension:
    """Temporary destination circuit-breaker state."""

    destination: str
    suspended_until: datetime | None = None
    reason: str | None = None
    manual: bool = True


@runtime_checkable
class DestinationSuspensionState(SyncState, Protocol):
    """State backend that can temporarily suspend a failing destination."""

    def get_destination_suspension(
        self,
        destination: str,
        *,
        now: datetime | None = None,
    ) -> DestinationSuspension | None:
        """Return an active suspension for a destination, if one exists."""

    def mark_destination_suspended(
        self,
        destination: str,
        *,
        until: datetime | None = None,
        reason: str | None = None,
    ) -> None:
        """Persist a suspension for a destination."""

    def clear_destination_suspension(self, destination: str) -> None:
        """Clear a destination suspension after a successful provider call."""


class FileSyncState:
    """File-backed sync state for local duplicate prevention."""

    def __init__(self, path: str | Path = DEFAULT_SYNC_STATE_PATH) -> None:
        self.path = Path(path)
        self._synced_keys, self._destination_suspensions = self._load()

    @classmethod
    def from_env(cls, env_var: str = SYNC_STATE_ENV_VAR) -> "FileSyncState":
        """Create state from an environment variable or the default local path."""

        return cls(os.environ.get(env_var, DEFAULT_SYNC_STATE_PATH))

    def is_synced(self, sync_key: str) -> bool:
        return sync_key in self._synced_keys

    def mark_synced(self, sync_key: str) -> None:
        if not isinstance(sync_key, str) or not sync_key:
            raise ValueError("sync_key must be a non-empty string")

        if sync_key in self._synced_keys:
            return

        self._synced_keys.add(sync_key)
        self._save()

    def get_destination_suspension(
        self,
        destination: str,
        *,
        now: datetime | None = None,
    ) -> DestinationSuspension | None:
        return _active_destination_suspension(
            self._destination_suspensions,
            destination,
            now=now,
        )

    def mark_destination_suspended(
        self,
        destination: str,
        *,
        until: datetime | None = None,
        reason: str | None = None,
    ) -> None:
        destination_key = _destination_key(destination)
        self._destination_suspensions[destination_key] = DestinationSuspension(
            destination=destination_key,
            suspended_until=_as_utc(until) if until is not None else None,
            reason=reason,
            manual=until is None,
        )
        self._save()

    def clear_destination_suspension(self, destination: str) -> None:
        destination_key = _destination_key(destination)
        if destination_key not in self._destination_suspensions:
            return
        del self._destination_suspensions[destination_key]
        self._save()

    def _load(self) -> tuple[set[str], dict[str, DestinationSuspension]]:
        if not self.path.exists():
            return set(), {}

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid sync state JSON: {self.path}") from exc

        return _parse_sync_state(raw)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = _sync_state_payload(
            self._synced_keys,
            self._destination_suspensions,
        )
        temp_path = self.path.with_name(f"{self.path.name}.tmp")
        temp_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(self.path)


class CloudStorageSyncState:
    """Google Cloud Storage-backed sync state for cloud duplicate prevention."""

    def __init__(self, bucket_name: str, blob_name: str, *, client: Any | None = None) -> None:
        self.bucket_name = _required_value(bucket_name, "bucket_name")
        self.blob_name = _required_value(blob_name, "blob_name")
        self._client = client or _default_storage_client()
        self._bucket = self._client.bucket(self.bucket_name)
        self._blob = self._bucket.blob(self.blob_name)
        self._synced_keys, self._destination_suspensions = self._load()

    @classmethod
    def from_env(cls) -> "CloudStorageSyncState":
        """Create state from Google Cloud Storage environment variables."""

        bucket_name = os.environ.get(GCS_SYNC_STATE_BUCKET_ENV_VAR, "")
        blob_name = os.environ.get(
            GCS_SYNC_STATE_BLOB_ENV_VAR,
            DEFAULT_GCS_SYNC_STATE_BLOB,
        )
        return cls(bucket_name, blob_name)

    def is_synced(self, sync_key: str) -> bool:
        return sync_key in self._synced_keys

    def mark_synced(self, sync_key: str) -> None:
        if not isinstance(sync_key, str) or not sync_key:
            raise ValueError("sync_key must be a non-empty string")

        if sync_key in self._synced_keys:
            return

        self._synced_keys.add(sync_key)
        self._save()

    def get_destination_suspension(
        self,
        destination: str,
        *,
        now: datetime | None = None,
    ) -> DestinationSuspension | None:
        return _active_destination_suspension(
            self._destination_suspensions,
            destination,
            now=now,
        )

    def mark_destination_suspended(
        self,
        destination: str,
        *,
        until: datetime | None = None,
        reason: str | None = None,
    ) -> None:
        destination_key = _destination_key(destination)
        self._destination_suspensions[destination_key] = DestinationSuspension(
            destination=destination_key,
            suspended_until=_as_utc(until) if until is not None else None,
            reason=reason,
            manual=until is None,
        )
        self._save()

    def clear_destination_suspension(self, destination: str) -> None:
        destination_key = _destination_key(destination)
        if destination_key not in self._destination_suspensions:
            return
        del self._destination_suspensions[destination_key]
        self._save()

    def _load(self) -> tuple[set[str], dict[str, DestinationSuspension]]:
        if not self._blob.exists():
            return set(), {}

        try:
            raw = json.loads(self._blob.download_as_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid sync state JSON in gs://{self.bucket_name}/{self.blob_name}"
            ) from exc

        return _parse_sync_state(raw)

    def _save(self) -> None:
        payload = _sync_state_payload(
            self._synced_keys,
            self._destination_suspensions,
        )
        self._blob.upload_from_string(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            content_type="application/json",
        )


def build_sync_state_from_env() -> SyncState:
    """Build the configured duplicate-prevention state backend."""

    backend = os.environ.get(SYNC_STATE_BACKEND_ENV_VAR, "file").strip().lower()
    if backend == "file":
        return FileSyncState.from_env()
    if backend in {"gcs", "cloud-storage", "cloud_storage"}:
        return CloudStorageSyncState.from_env()
    raise ValueError(
        f"{SYNC_STATE_BACKEND_ENV_VAR} must be one of: file, gcs"
    )


def _parse_synced_keys(raw: Any) -> set[str]:
    if not isinstance(raw, dict):
        raise ValueError("sync state file must contain a JSON object")

    raw_keys = raw.get("synced_weight_keys", [])
    if not isinstance(raw_keys, list) or not all(
        isinstance(key, str) for key in raw_keys
    ):
        raise ValueError("sync state synced_weight_keys must be a list of strings")

    return set(raw_keys)


def _parse_sync_state(raw: Any) -> tuple[set[str], dict[str, DestinationSuspension]]:
    synced_keys = _parse_synced_keys(raw)
    suspensions: dict[str, DestinationSuspension] = {}
    raw_suspensions = raw.get("destination_suspensions", {})
    if raw_suspensions is None:
        raw_suspensions = {}
    if not isinstance(raw_suspensions, dict):
        raise ValueError("sync state destination_suspensions must be a JSON object")

    for destination, value in raw_suspensions.items():
        if not isinstance(destination, str) or not isinstance(value, dict):
            raise ValueError("sync state destination_suspensions entries are invalid")
        raw_until = value.get("suspended_until")
        if raw_until is not None and not isinstance(raw_until, str):
            raise ValueError("destination suspension suspended_until must be a string")
        reason = value.get("reason")
        if reason is not None and not isinstance(reason, str):
            raise ValueError("destination suspension reason must be a string")
        manual = value.get("manual", raw_until is None)
        if not isinstance(manual, bool):
            raise ValueError("destination suspension manual must be a bool")
        suspensions[_destination_key(destination)] = DestinationSuspension(
            destination=_destination_key(destination),
            suspended_until=_parse_datetime(raw_until) if raw_until is not None else None,
            reason=reason,
            manual=manual,
        )

    return synced_keys, suspensions


def _sync_state_payload(
    synced_keys: set[str],
    destination_suspensions: dict[str, DestinationSuspension],
) -> dict[str, Any]:
    payload: dict[str, Any] = {"synced_weight_keys": sorted(synced_keys)}
    active_suspensions = {
        destination: _destination_suspension_payload(suspension)
        for destination, suspension in sorted(destination_suspensions.items())
    }
    if active_suspensions:
        payload["destination_suspensions"] = active_suspensions
    return payload


def _active_destination_suspension(
    suspensions: dict[str, DestinationSuspension],
    destination: str,
    *,
    now: datetime | None,
) -> DestinationSuspension | None:
    destination_key = _destination_key(destination)
    suspension = suspensions.get(destination_key)
    if suspension is None:
        return None
    if suspension.manual:
        return suspension
    if suspension.suspended_until is None:
        return suspension
    if suspension.suspended_until <= _as_utc(now or datetime.now(UTC)):
        return None
    return suspension


def _destination_suspension_payload(
    suspension: DestinationSuspension,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "manual": suspension.manual,
        "reason": suspension.reason,
    }
    if suspension.suspended_until is not None:
        payload["suspended_until"] = suspension.suspended_until.isoformat()
    return payload


def _destination_key(destination: str) -> str:
    cleaned = destination.strip().lower()
    if not cleaned:
        raise ValueError("destination must not be empty")
    return cleaned


def _parse_datetime(value: str) -> datetime:
    return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _required_value(value: str, name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{name} must not be empty")
    return cleaned


def _default_storage_client() -> Any:
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError(
            "google-cloud-storage is not installed; install runtime dependencies"
        ) from exc

    return storage.Client()


__all__ = [
    "CloudStorageSyncState",
    "DEFAULT_GCS_SYNC_STATE_BLOB",
    "DEFAULT_SYNC_STATE_PATH",
    "DestinationSuspension",
    "DestinationSuspensionState",
    "GCS_SYNC_STATE_BLOB_ENV_VAR",
    "GCS_SYNC_STATE_BUCKET_ENV_VAR",
    "SYNC_STATE_ENV_VAR",
    "SYNC_STATE_BACKEND_ENV_VAR",
    "FileSyncState",
    "SyncState",
    "build_sync_state_from_env",
]
