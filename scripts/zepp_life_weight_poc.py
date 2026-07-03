"""Read the latest weight record from a Zepp Life export CSV or ZIP.

This is intentionally a tiny POC, not the final source adapter. It accepts the
file shapes we expect from Zepp/Mi Fit exports and emits JSON shaped like the
future canonical WeightMeasurement model.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

SAMPLE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "samples" / "zepp_life_body_sample.csv"
)

TIME_COLUMNS = ("time", "date", "datetime", "timestamp", "measured_at", "start_time")
WEIGHT_COLUMNS = ("weight", "weight_kg", "body_weight", "value")
BODY_FAT_COLUMNS = ("fat", "body_fat", "body_fat_percent", "fat_rate")
MUSCLE_COLUMNS = ("muscle", "muscle_mass", "muscle_mass_kg")


@dataclass(frozen=True)
class POCWeightRecord:
    measured_at: datetime
    weight_kg: float
    body_fat_percent: float | None
    muscle_mass_kg: float | None
    raw_file: str
    raw_row_number: int

    def to_json_dict(self) -> dict[str, object]:
        metadata = {
            "raw_file": self.raw_file,
            "raw_row_number": self.raw_row_number,
        }
        return {
            "source": "zepp_life_export",
            "measured_at": self.measured_at.isoformat(),
            "weight_kg": self.weight_kg,
            "body_fat_percent": self.body_fat_percent,
            "muscle_mass_kg": self.muscle_mass_kg,
            "metadata": metadata,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        help="Path to a Zepp export .zip, unpacked export directory, or BODY_*.csv file.",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Read the bundled sample file instead of a private export.",
    )
    args = parser.parse_args()

    if args.sample == bool(args.input):
        parser.error("Choose exactly one of --sample or --input.")

    input_path = SAMPLE_PATH if args.sample else args.input
    assert input_path is not None

    try:
        latest = latest_weight_record(input_path)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"Zepp Life weight POC failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(latest.to_json_dict(), indent=2, sort_keys=True))
    return 0


def latest_weight_record(input_path: Path) -> POCWeightRecord:
    records = list(iter_weight_records(input_path))
    if not records:
        raise ValueError(f"No weight records found in {input_path}")
    return max(records, key=lambda record: record.measured_at)


def iter_weight_records(input_path: Path) -> Iterable[POCWeightRecord]:
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    if input_path.is_dir():
        csv_paths = sorted(input_path.rglob("BODY*.csv"))
        if not csv_paths:
            raise ValueError(f"No BODY*.csv files found under {input_path}")
        for csv_path in csv_paths:
            yield from parse_csv_text(
                csv_path.read_text(encoding="utf-8-sig"), str(csv_path)
            )
        return

    if input_path.suffix.lower() == ".zip":
        with ZipFile(input_path) as export_zip:
            body_members = [
                name
                for name in export_zip.namelist()
                if Path(name).name.upper().startswith("BODY")
                and name.lower().endswith(".csv")
            ]
            if not body_members:
                raise ValueError(f"No BODY*.csv files found in {input_path}")
            for member in sorted(body_members):
                data = export_zip.read(member).decode("utf-8-sig")
                yield from parse_csv_text(data, member)
        return

    if input_path.suffix.lower() != ".csv":
        raise ValueError(f"Expected a .zip, directory, or .csv file: {input_path}")

    yield from parse_csv_text(input_path.read_text(encoding="utf-8-sig"), str(input_path))


def parse_csv_text(csv_text: str, raw_file: str) -> Iterable[POCWeightRecord]:
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        return

    normalized_fields = {normalize_key(field): field for field in reader.fieldnames}
    time_column = first_matching_column(normalized_fields, TIME_COLUMNS)
    weight_column = first_matching_column(normalized_fields, WEIGHT_COLUMNS)
    fat_column = first_matching_column(
        normalized_fields, BODY_FAT_COLUMNS, required=False
    )
    muscle_column = first_matching_column(
        normalized_fields, MUSCLE_COLUMNS, required=False
    )

    for row_number, row in enumerate(reader, start=2):
        measured_at = parse_datetime(row.get(time_column, ""))
        weight_kg = parse_float(row.get(weight_column, ""))
        if measured_at is None or weight_kg is None:
            continue

        yield POCWeightRecord(
            measured_at=measured_at,
            weight_kg=weight_kg,
            body_fat_percent=parse_float(row.get(fat_column, "")) if fat_column else None,
            muscle_mass_kg=parse_float(row.get(muscle_column, ""))
            if muscle_column
            else None,
            raw_file=raw_file,
            raw_row_number=row_number,
        )


def first_matching_column(
    normalized_fields: dict[str, str],
    candidates: tuple[str, ...],
    *,
    required: bool = True,
) -> str | None:
    for candidate in candidates:
        if candidate in normalized_fields:
            return normalized_fields[candidate]
    if required:
        available = ", ".join(sorted(normalized_fields))
        expected = ", ".join(candidates)
        raise KeyError(
            f"Missing expected column. Expected one of [{expected}], got [{available}]"
        )
    return None


def normalize_key(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return float(cleaned)


def parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    for date_format in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
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


if __name__ == "__main__":
    raise SystemExit(main())
