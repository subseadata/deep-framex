import pytest
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from soi_frame_extractor.data.importer import import_csv
from soi_frame_extractor.db.session_db import create_session_db
from soi_frame_extractor.models.models import ColumnMappings


# Fixture: fresh in-memory DB for each test.
@pytest.fixture
def conn():
    c = create_session_db()
    yield c
    c.close()


# Fixture: minimal valid CSV written to tmp_path.
@pytest.fixture
def csv_path(tmp_path):
    p = tmp_path / "sensor.csv"
    p.write_text("Timestamp,Depth_m,Temp_C\n"
               "2025-10-15T10:00:00Z,371.2,2.0\n"
               "2025-10-15T10:00:30Z,372.5,1.9\n")
    return p


# Correct row count, columns, and UTC time range returned.
def test_import_valid_csv(conn, csv_path):
    mappings = ColumnMappings(timestamp="Timestamp", depth="Depth_m", temp="Temp_C")
    dataset = import_csv(csv_path, conn, mappings)
    assert dataset.row_count == 2
    assert dataset.timestamp_column == "Timestamp" 
    assert dataset.columns == ["depth", "temp"]
    assert dataset.utc_start == datetime(2025, 10, 15, 10, 0, 0, tzinfo=timezone.utc)
    assert dataset.utc_end == datetime(2025, 10, 15, 10, 0, 30, tzinfo=timezone.utc)

# Only mapped columns land in the DB — unmapped CSV columns are ignored.
def test_only_mapped_columns_imported(conn, csv_path):
    mappings = ColumnMappings(timestamp="Timestamp", depth="Depth_m")
    dataset = import_csv(csv_path, conn, mappings)
    assert dataset.columns == ["depth"]

# Timestamp column missing from CSV headers.
def test_missing_timestamp_column_raises(conn, tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("Timestamp,Depth_m,Temp_C\n"
               "2025-10-15T10:00:00Z,371.2,2.0\n"
               "2025-10-15T10:00:30Z,372.5,1.9\n")
    mappings = ColumnMappings(timestamp="WrongColumn", depth="Depth_m")
    with pytest.raises(ValueError):
        dataset = import_csv(p, conn, mappings)

# Non-numeric sensor value raises.
def test_non_numeric_sensor_raises(conn, tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("Timestamp,Depth_m,Temp_C\n"
               "2025-10-15T10:00:00Z,banana,2.0\n"
               "2025-10-15T10:00:30Z,372.5,1.9\n")
    mappings = ColumnMappings(timestamp="Timestamp", depth="Depth_m", temp="Temp_C")
    with pytest.raises(ValueError):
        dataset = import_csv(p, conn, mappings)

# Naive timestamp (no timezone) raises.
def test_naive_timestamp_raises(conn, tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("Timestamp,Depth_m,Temp_C\n"
               "2025-10-15T10:00:00,371.2,2.0\n"
               "2025-10-15T10:00:30,372.5,1.9\n")
    mappings = ColumnMappings(timestamp="Timestamp", depth="Depth_m")
    with pytest.raises(ValueError):
        dataset = import_csv(p, conn, mappings)

# Empty CSV (headers only, no data rows) raises.
def test_empty_csv_raises(conn, tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("Timestamp,Depth_m,Temp_C\n")
    mappings = ColumnMappings(timestamp="Timestamp", depth="Depth_m")
    with pytest.raises(ValueError):
        dataset = import_csv(p, conn, mappings)

