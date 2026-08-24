import pytest
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone
from deep_framex.data.importer import import_csv
from deep_framex.db.session_db import create_session_db
from deep_framex.models.core import ColumnMappings


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


# Helper: stored timestamps as UTC datetimes, in ascending order.
def _stored_times(conn):
    return [
        datetime.fromtimestamp(row[0], tz=timezone.utc)
        for row in conn.execute("SELECT timestamp FROM sensor_readings ORDER BY timestamp")
    ]


# time_shift moves every stored timestamp by the same amount.
def test_time_shift_applied(conn, csv_path):
    mappings = ColumnMappings(timestamp="Timestamp", depth="Depth_m")
    dataset = import_csv(csv_path, conn, mappings, time_shift=timedelta(minutes=90))
    assert _stored_times(conn) == [
        datetime(2025, 10, 15, 11, 30, 0, tzinfo=timezone.utc),
        datetime(2025, 10, 15, 11, 30, 30, tzinfo=timezone.utc),
    ]
    assert dataset.utc_start == datetime(2025, 10, 15, 11, 30, 0, tzinfo=timezone.utc)
    assert dataset.utc_end == datetime(2025, 10, 15, 11, 30, 30, tzinfo=timezone.utc)


# A negative time_shift moves timestamps earlier.
def test_negative_time_shift_applied(conn, csv_path):
    mappings = ColumnMappings(timestamp="Timestamp", depth="Depth_m")
    import_csv(csv_path, conn, mappings, time_shift=timedelta(seconds=-45))
    assert _stored_times(conn)[0] == datetime(2025, 10, 15, 9, 59, 15, tzinfo=timezone.utc)


# start_time places the earliest reading exactly, preserving the gaps.
def test_start_time_anchors_earliest_reading(conn, csv_path):
    mappings = ColumnMappings(timestamp="Timestamp", depth="Depth_m")
    anchor = datetime(2025, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    import_csv(csv_path, conn, mappings, start_time=anchor)
    times = _stored_times(conn)
    assert times == [anchor, anchor + timedelta(seconds=30)]


# Row order in the CSV is not assumed — the anchor is the earliest reading, not row 0.
def test_start_time_anchors_on_earliest_not_first_row(conn, tmp_path):
    p = tmp_path / "unsorted.csv"
    p.write_text("Timestamp,Depth_m\n"
                 "2025-10-15T10:00:30Z,372.5\n"
                 "2025-10-15T10:00:00Z,371.2\n")
    anchor = datetime(2025, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    import_csv(p, conn, ColumnMappings(timestamp="Timestamp", depth="Depth_m"), start_time=anchor)
    assert _stored_times(conn) == [anchor, anchor + timedelta(seconds=30)]


# Sensor values travel with their shifted timestamps.
def test_shift_preserves_sensor_values(conn, csv_path):
    mappings = ColumnMappings(timestamp="Timestamp", depth="Depth_m")
    import_csv(csv_path, conn, mappings, time_shift=timedelta(minutes=90))
    rows = conn.execute("SELECT depth FROM sensor_readings ORDER BY timestamp").fetchall()
    assert [r[0] for r in rows] == [371.2, 372.5]
