"""Data importer

Loads a user-supplied CSV into the session database sensor_readings table.

The CSV must contain a timestamp column named in the ColumnMappings.  All
other columns are treated as sensor readings and stored under their original
names.  Column names become SQL column names and are validated as legal
identifiers at import time.

No assumptions are made about which sensor columns are present.  One column
is the minimum; any number beyond that are equally valid.

Timestamps are parsed as ISO 8601 UTC and stored as Unix epoch floats for
efficient range queries during planning.  Columns that cannot be cast to
float are rejected with a descriptive error rather than silently dropped.
"""

import sqlite3
from pathlib import Path

from ..db.session_db import init_sensor_table
from ..models.models import ImportedDataset


def import_csv(
    path: Path,
    conn: sqlite3.Connection,
    timestamp_column: str,
) -> ImportedDataset:
    """Load a CSV file into the session database sensor_readings table.

    Reads the CSV, validates column names and data types, creates the
    sensor_readings table via init_sensor_table, and inserts all rows.
    Returns an ImportedDataset describing what was loaded.

    Args:
        path:             path to the CSV file.
        conn:             active session database connection.
        timestamp_column: name of the column containing UTC timestamps,
                          taken from ColumnMappings.timestamp.

    Returns:
        ImportedDataset with column names, row count, and UTC time range
        of the imported data.

    Raises:
        FileNotFoundError: if path does not exist.
        ValueError: if timestamp_column is not found in the CSV headers.
        ValueError: if any column name fails identifier validation.
        ValueError: if any timestamp string is not valid ISO 8601 UTC.
        ValueError: if any non-timestamp cell cannot be cast to float.
    """
    pass


def _validate_columns(columns: list[str]) -> None:
    """Raise ValueError if any column name is not a valid SQL identifier.

    A valid identifier starts with a letter or underscore and contains only
    letters, digits, and underscores.

    Args:
        columns: column names to validate.

    Raises:
        ValueError: naming the first offending column.
    """
    pass


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
    pass
