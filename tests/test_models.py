from datetime import datetime, timezone

import pytest

from healthsync.models import WeightMeasurement


def test_weight_measurement_accepts_canonical_fields() -> None:
    measurement = WeightMeasurement(
        source=" file_weight ",
        measured_at=datetime(2026, 6, 27, 9, 30, tzinfo=timezone.utc),
        weight_kg=72,
        body_fat_percent=18.5,
        muscle_mass_kg=54.2,
        metadata={"provider_id": "abc123"},
    )

    assert measurement.source == "file_weight"
    assert measurement.weight_kg == 72.0
    assert measurement.body_fat_percent == 18.5
    assert measurement.muscle_mass_kg == 54.2
    assert measurement.metadata == {"provider_id": "abc123"}


def test_sync_key_is_stable_for_duplicate_detection() -> None:
    measured_at = datetime(2026, 6, 27, 9, 30, tzinfo=timezone.utc)

    first = WeightMeasurement(
        source="file_weight",
        measured_at=measured_at,
        weight_kg=72,
        metadata={"import_row": 1},
    )
    second = WeightMeasurement(
        source="file_weight",
        measured_at=measured_at,
        weight_kg=72.0,
        metadata={"import_row": 99},
    )

    assert first.sync_key == second.sync_key


def test_sync_key_changes_when_duplicate_identity_changes() -> None:
    first = WeightMeasurement(
        source="file_weight",
        measured_at=datetime(2026, 6, 27, 9, 30, tzinfo=timezone.utc),
        weight_kg=72,
    )
    second = WeightMeasurement(
        source="file_weight",
        measured_at=datetime(2026, 6, 28, 9, 30, tzinfo=timezone.utc),
        weight_kg=72,
    )

    assert first.sync_key != second.sync_key


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source", "", "source is required"),
        ("measured_at", None, "measured_at must be a datetime"),
        ("weight_kg", 0, "weight_kg must be a positive finite number"),
        ("weight_kg", -1, "weight_kg must be a positive finite number"),
        ("weight_kg", float("nan"), "weight_kg must be a positive finite number"),
        ("body_fat_percent", 101, "body_fat_percent must be at most 100"),
        ("muscle_mass_kg", -1, "muscle_mass_kg must be at least 0"),
        ("metadata", [], "metadata must be a dict"),
    ],
)
def test_weight_measurement_rejects_invalid_values(
    field: str,
    value: object,
    message: str,
) -> None:
    kwargs = {
        "source": "file_weight",
        "measured_at": datetime(2026, 6, 27, 9, 30, tzinfo=timezone.utc),
        "weight_kg": 72,
    }
    kwargs[field] = value

    with pytest.raises(ValueError, match=message):
        WeightMeasurement(**kwargs)
