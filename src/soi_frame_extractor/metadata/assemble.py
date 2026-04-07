"""BIIGLE record assembler

Builds the list[tuple[Path, FrameMetadata]] input that write_biigle_manifest
expects, from a flat file list with timestamps and an optional sensor CSV.

This is the entry point for generating BIIGLE metadata without running the
full extraction pipeline — no video files or pixel data are required.  The
caller supplies filenames and UTC timestamps (however they were obtained),
and this module handles sensor interpolation and model construction.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from ..data.importer import import_csv
from ..db.session_db import create_session_db, close_session_db
from ..models.models import ColumnMappings, FrameMetadata
from ..planning.planner import interpolate_sensor


def assemble_biigle_records(
    files: list[tuple[str, datetime]],
    csv_path: Path | None = None,
    mappings: ColumnMappings | None = None,
    project_metadata: dict[str, str] = {},
    interpolation_window: int = 2,
) -> list[tuple[Path, FrameMetadata]]:
    """Build BIIGLE-ready records from a file list and optional sensor CSV.

    No image files are opened or required — only the filenames and their UTC
    timestamps are used.  If a sensor CSV is provided, sensor values are
    interpolated at each file's timestamp and embedded in the record.

    Args:
        files:                list of (filename, utc_timestamp) pairs.
                              Filenames are used verbatim as the BIIGLE
                              'filename' column; they need not exist on disk.
        csv_path:             path to sensor CSV file, or None for no sensor data.
        mappings:             ColumnMappings describing the CSV columns.
                              Required if csv_path is provided.
        project_metadata:     arbitrary key/value pairs embedded in every record.
        interpolation_window: number of sensor rows to use on each side when
                              interpolating.  Default 2.

    Returns:
        list of (Path(filename), FrameMetadata) pairs suitable for passing
        directly to write_biigle_manifest.

    Raises:
        ValueError: if csv_path is provided without mappings, or if mappings
                    is provided without csv_path.
        FileNotFoundError: if csv_path does not exist.
    """
    if csv_path is not None and mappings is None:
        raise ValueError(
            "csv_path was provided but mappings is None. "
            "Supply a ColumnMappings instance describing the CSV columns."
        )
    if mappings is not None and csv_path is None:
        raise ValueError(
            "mappings was provided but csv_path is None. "
            "Supply a csv_path to load sensor data from."
        )

    conn: sqlite3.Connection = create_session_db()
    try:
        sensor_cols: list[str] = []
        if csv_path is not None and mappings is not None:
            dataset = import_csv(csv_path, conn, mappings)
            sensor_cols = dataset.columns

        records: list[tuple[Path, FrameMetadata]] = []
        for filename, utc in files:
            snapshot = (
                interpolate_sensor(utc.timestamp(), sensor_cols, conn, interpolation_window)
                if sensor_cols else {}
            )
            meta = FrameMetadata(
                utc_timestamp=utc,
                video_path=Path(filename),
                offset_s=0.0,
                sensor_snapshot=snapshot,
                project_metadata=project_metadata,
            )
            records.append((Path(filename), meta))
    finally:
        close_session_db(conn)

    return records
