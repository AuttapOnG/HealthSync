"""Sync state backends for duplicate prevention."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol, runtime_checkable


DEFAULT_SYNC_STATE_PATH = Path("data/sync_state.json")
SYNC_STATE_ENV_VAR = "HEALTHSYNC_SYNC_STATE_PATH"


@runtime_checkable
class SyncState(Protocol):
    """State backend that tracks successfully synced measurement keys."""

    def is_synced(self, sync_key: str) -> bool:
        """Return whether a sync key has already been uploaded successfully."""

    def mark_synced(self, sync_key: str) -> None:
        """Persist a sync key after a successful upload."""


class FileSyncState:
    """File-backed sync state for local duplicate prevention."""

    def __init__(self, path: str | Path = DEFAULT_SYNC_STATE_PATH) -> None:
        self.path = Path(path)
        self._synced_keys = self._load()

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

    def _load(self) -> set[str]:
        if not self.path.exists():
            return set()

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid sync state JSON: {self.path}") from exc

        if not isinstance(raw, dict):
            raise ValueError("sync state file must contain a JSON object")

        raw_keys = raw.get("synced_weight_keys", [])
        if not isinstance(raw_keys, list) or not all(
            isinstance(key, str) for key in raw_keys
        ):
            raise ValueError("sync state synced_weight_keys must be a list of strings")

        return set(raw_keys)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"synced_weight_keys": sorted(self._synced_keys)}
        temp_path = self.path.with_name(f"{self.path.name}.tmp")
        temp_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(self.path)


__all__ = [
    "DEFAULT_SYNC_STATE_PATH",
    "SYNC_STATE_ENV_VAR",
    "FileSyncState",
    "SyncState",
]
