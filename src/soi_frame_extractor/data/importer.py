"""Data importer

Loads a user-supplied CSV into the session database sensor_readings table.

Only columns listed in the user's mappings block are imported — every other
column in the CSV is ignored.  The mappings block pairs the name the tool
will use (left side) with the exact column header in the CSV (right side):

    depth: Depth_m          →  read "Depth_m" from CSV, store as "depth"
    latitude: Latitude_ddeg →  read "Latitude_ddeg" from CSV, store as "latitude"

The left-side names become the column names in the database and are used
everywhere downstream: in constraint rules, filename templates, and metadata
output.  The right-side CSV column names are only used here at import time
and are not stored anywhere.

Timestamps are parsed as ISO 8601 UTC and stored as Unix epoch floats for
efficient range queries during planning.  All sensor values must be numeric.
"""

import csv
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ..db.session_db import init_sensor_table
from ..models.models import ColumnMappings, ImportedDataset


def import_csv(
    path: Path,
    conn: sqlite3.Connection,
    mappings: ColumnMappings,
) -> ImportedDataset:
    """Load a CSV file into the session database sensor_readings table.

    Reads only the columns named in mappings spec from YAML.  Canonical 
    names (the keys of mappings) become the DB column names.  The
    timestamp column is always stored as 'timestamp' in the DB regardless 
    of its CSV column name.

    Args:
        path:     path to the CSV file.
        conn:     active session database connection.
        mappings: ColumnMappings from the ExtractionSpec.  Only columns
                  listed here are imported; everything else is ignored.

    Returns:
        ImportedDataset with canonical column names, row count, and UTC
        time range of the imported data.

    Raises:
        FileNotFoundError: if path does not exist.
        ValueError: if any mapped CSV column is not found in the CSV headers.
        ValueError: if any canonical name fails SQL identifier validation.
        ValueError: if any timestamp string is not valid ISO 8601 UTC.
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

    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        headers = set(reader.fieldnames or [])

        # Verify all mapped CSV columns actually exist in the file
        if mappings.timestamp not in headers:
            raise ValueError(
                f"Timestamp column {mappings.timestamp!r} not found in CSV. "
                f"Available columns: {sorted(headers)}"
            )
        for canonical, csv_col in canonical_to_csv.items():
            if csv_col not in headers:
                raise ValueError(
                    f"Mapped column {csv_col!r} (for canonical name {canonical!r}) "
                    f"not found in CSV. Available columns: {sorted(headers)}"
                )

        init_sensor_table(conn, list(canonical_to_csv.keys()))

        rows: list[tuple] = []
        timestamps: list[float] = []
        for i, row in enumerate(reader):
            ts = _parse_timestamp(row[mappings.timestamp])

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

    placeholders = ", ".join(["?"] * (1 + len(canonical_to_csv)))
    conn.executemany(f"INSERT INTO sensor_readings VALUES ({placeholders})", rows)
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


def _parse_timestamp(value: str) -> float:
    """Parse an ISO 8601 UTC timestamp string to a Unix epoch float.

    Args:
        value: ISO 8601 string with an explicit UTC offset (Z or +00:00).

    Returns:
        Seconds since Unix epoch as a float.

    Raises:
        ValueError: if the string is not parseable as a datetime.
        ValueError: if the parsed datetime has no timezone info (naive).
    """
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError(f"Timestamp is not UTC-aware: {value!r}")
    return dt.timestamp()
