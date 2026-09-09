"""Data importer

Loads a user-supplied CSV into a session database sensor readings table.

One table per CSV, named by the caller, so each file keeps its own timestamp
grid and several sensor files can be loaded into one session.

Only columns listed in the user's mappings block are imported — every other
column in the CSV is ignored.  The mappings block pairs the name the tool
will use (left side) with the exact column header in the CSV (right side):

    depth: Depth_m          →  read "Depth_m" from CSV, store as "depth"
    latitude: Latitude_ddeg →  read "Latitude_ddeg" from CSV, store as "latitude"

The left-side names become the column names in the database and are used
everywhere downstream: in constraint rules, filename templates, and metadata
output.  The right-side CSV column names are only used here at import time
and are not stored anywhere.

Timestamps are parsed as ISO 8601, or with the strptime format given by
mappings.timestamp_format, and stored as Unix epoch floats for efficient range
queries during planning.  Timestamps without a timezone are assumed to be UTC.
The time reference may live in one column or be split across several (e.g.
separate date and time columns), in which case the cells are joined with a
single space before parsing.  All sensor values must be numeric.

If the sensor logger's clock was offset from the video clock, time_shift or
start_time realign the imported timestamps — see import_csv.
"""

import csv
import re
import sqlite3
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..db.session_db import init_sensor_table
from ..models.core import ColumnMappings, ImportedDataset


def import_csv(
    path: Path,
    conn: sqlite3.Connection,
    mappings: ColumnMappings,
    time_shift: timedelta | None = None,
    start_time: datetime | None = None,
    table: str = "sensor_readings",
) -> ImportedDataset:
    """Load a CSV file into a session database sensor readings table.

    Reads only the columns named in mappings spec from YAML.  Canonical 
    names (the keys of mappings) become the DB column names.  The
    timestamp column is always stored as 'timestamp' in the DB regardless 
    of its CSV column name(s).

    Args:
        path:     path to the CSV file.
        conn:     active session database connection.
        mappings: ColumnMappings from the ExtractionSpec.  Only columns
                  listed here are imported; everything else is ignored.
        time_shift: duration added to every imported timestamp.  Use this when
                  the sensor clock ran ahead of or behind the video clock by a
                  known amount.  May be negative.
        start_time: UTC time to place the earliest reading at.  Every timestamp
                  is shifted by the same delta, so the spacing between readings
                  is preserved.  Note this anchors on the earliest reading, not
                  on the first CSV row — row order in the file is not assumed.
        table:    name of the table to load into.  One table per sensor CSV, so
                  each file keeps its own timestamp grid.

    time_shift and start_time are alternative ways to express the same
    correction; the spec parser rejects specs that set both.

    Returns:
        ImportedDataset with canonical column names, row count, and UTC
        time range of the imported data.

    Raises:
        FileNotFoundError: if path does not exist.
        ValueError: if any mapped CSV column is not found in the CSV headers.
        ValueError: if any canonical name fails SQL identifier validation.
        ValueError: if any timestamp string matches neither ISO 8601 nor
            mappings.timestamp_format.
        ValueError: if any sensor cell cannot be cast to float.
        ValueError: if the CSV contains no data rows.
    """
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    # Build canonical → csv_column mapping for non-timestamp fields
    canonical_to_csv: dict[str, str] = {}
    for field in ("latitude", "longitude", "depth"):
        csv_col = getattr(mappings, field)
        if csv_col is not None:
            canonical_to_csv[field] = csv_col
    canonical_to_csv.update(mappings.model_extra or {})

    # Canonical names become DB column names — must be valid SQL identifiers
    _validate_columns(list(canonical_to_csv.keys()))

    ts_cols = (
        [mappings.timestamp] if isinstance(mappings.timestamp, str) else mappings.timestamp
    )

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = set(reader.fieldnames or [])

        # Verify all mapped CSV columns actually exist in the file
        for ts_col in ts_cols:
            if ts_col not in headers:
                raise ValueError(
                    f"Timestamp column {ts_col!r} not found in CSV. "
                    f"Available columns: {sorted(headers)}"
                )
        for canonical, csv_col in canonical_to_csv.items():
            if csv_col not in headers:
                raise ValueError(
                    f"Mapped column {csv_col!r} (for canonical name {canonical!r}) "
                    f"not found in CSV. Available columns: {sorted(headers)}"
                )

        init_sensor_table(conn, list(canonical_to_csv.keys()), table)

        rows: list[tuple] = []
        timestamps: list[float] = []
        for i, row in enumerate(reader):
            ts = _parse_timestamp(
                " ".join(row[c] for c in ts_cols), mappings.timestamp_format
            )

            sensor_vals: list[float] = []
            for canonical, csv_col in canonical_to_csv.items():
                raw = row.get(csv_col, "")
                try:
                    sensor_vals.append(float(raw))
                except (ValueError, TypeError):
                    raise ValueError(
                        f"Row {i}: cannot cast {canonical!r} "
                        f"(CSV column {csv_col!r}) to float: {raw!r}"
                    )

            rows.append((ts, *sensor_vals))
            timestamps.append(ts)

    if not rows:
        raise ValueError(f"CSV file {path} contains no data rows")

    # Realign the sensor clock to the video clock.  Applied once here, after the
    # whole file is read, so start_time can anchor on the earliest reading — and
    # so everything downstream (constraint windows, interpolation) reads already
    # corrected timestamps and needs no knowledge of the shift.
    delta = 0.0
    if time_shift is not None:
        delta = time_shift.total_seconds()
    elif start_time is not None:
        delta = start_time.timestamp() - min(timestamps)
    if delta:
        rows = [(ts + delta, *vals) for ts, *vals in rows]
        timestamps = [ts + delta for ts in timestamps]

    placeholders = ", ".join(["?"] * (1 + len(canonical_to_csv)))
    conn.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', rows)
    conn.commit()

    return ImportedDataset(
        columns=list(canonical_to_csv.keys()),
        timestamp_column=mappings.timestamp,
        row_count=len(rows),
        utc_start=datetime.fromtimestamp(min(timestamps), tz=timezone.utc),
        utc_end=datetime.fromtimestamp(max(timestamps), tz=timezone.utc),
    )


def _validate_columns(columns: list[str]) -> None:
    """Raise ValueError if any left-side mapping name is not a valid identifier.

    The left-side names (what the tool calls the column) become database column
    names, so they must contain only letters, digits, and underscores and must
    start with a letter or underscore.  Special characters belong on the right
    side (the CSV column name), not the left.

    Args:
        columns: left-side mapping names to validate.

    Raises:
        ValueError: naming the first offending entry and explaining how to fix it.
    """
    pattern = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    for col in columns:
        if not pattern.match(col):
            raise ValueError(
                f"Canonical name {col!r} is not a valid SQL identifier. "
                "Rename it in the mappings block (letters, digits, underscores only; "
                "must start with a letter or underscore)."
            )


_AUTO_FORMATS = ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M")


def _parse_timestamp(value: str, fmt: str | None = None) -> float:
    """Parse a timestamp string to a Unix epoch float.

    Args:
        value: the timestamp string.  If the time reference is split across
               several CSV columns, the cells joined with a single space.
        fmt:   strptime format to parse value with.  If None, ISO 8601 is
               tried first, then the unambiguous formats in _AUTO_FORMATS.
               Day-first and month-first slash dates are indistinguishable,
               so those always need an explicit fmt.

    Returns:
        Seconds since Unix epoch as a float.

    Raises:
        ValueError: if the string matches neither ISO 8601 nor fmt.
    """
    if fmt is not None:
        dt = datetime.strptime(value, fmt)
    else:
        for f in (None, *_AUTO_FORMATS):
            try:
                dt = (
                    datetime.fromisoformat(value)
                    if f is None
                    else datetime.strptime(value, f)
                )
                break
            except ValueError:
                continue
        else:
            raise ValueError(
                f"Cannot parse timestamp {value!r}. Add 'timestamp_format' to the "
                "mappings block with a strptime format, e.g. '%d/%m/%Y %H:%M:%S'."
            )
    if dt.tzinfo is None:
        warnings.warn(
            "Sensor timestamps have no timezone — assuming UTC.",
            UserWarning,
            stacklevel=2,
        )
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()
