import pytest
from datetime import datetime, timezone
from pathlib import Path

from soi_frame_extractor.metadata.assemble import assemble_biigle_records
from soi_frame_extractor.models.models import ColumnMappings


T1 = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
T2 = datetime(2025, 6, 1, 12, 0, 5, tzinfo=timezone.utc)
T3 = datetime(2025, 6, 1, 12, 0, 10, tzinfo=timezone.utc)


@pytest.fixture
def sensor_csv(tmp_path):
    p = tmp_path / "sensor.csv"
    p.write_text(
        "Timestamp,Depth_m,Lat,Lon\n"
        "2025-06-01T11:59:58Z,100.0,-32.5,151.2\n"
        "2025-06-01T12:00:02Z,101.0,-32.6,151.3\n"
        "2025-06-01T12:00:07Z,102.0,-32.7,151.4\n"
        "2025-06-01T12:00:12Z,103.0,-32.8,151.5\n"
    )
    return p


@pytest.fixture
def mappings():
    return ColumnMappings(timestamp="Timestamp", depth="Depth_m", latitude="Lat", longitude="Lon")


# No sensor data: returns one record per file with empty snapshot.
def test_no_sensor_data():
    files = [("frame_001.jpg", T1), ("frame_002.jpg", T2)]
    records = assemble_biigle_records(files)
    assert len(records) == 2
    path, meta = records[0]
    assert path == Path("frame_001.jpg")
    assert meta.sensor_snapshot == {}
    assert meta.utc_timestamp == T1


# With sensor CSV: snapshots are populated via interpolation.
def test_with_sensor_csv(tmp_path, sensor_csv, mappings):
    files = [("frame_001.jpg", T1), ("frame_002.jpg", T2), ("frame_003.jpg", T3)]
    records = assemble_biigle_records(files, csv_path=sensor_csv, mappings=mappings)
    assert len(records) == 3
    for _, meta in records:
        assert "depth" in meta.sensor_snapshot
        assert "latitude" in meta.sensor_snapshot
        assert "longitude" in meta.sensor_snapshot


# project_metadata is embedded in every record.
def test_project_metadata_propagated():
    files = [("frame_001.jpg", T1), ("frame_002.jpg", T2)]
    proj = {"dive_id": "D001", "cruise_id": "FK999"}
    records = assemble_biigle_records(files, project_metadata=proj)
    for _, meta in records:
        assert meta.project_metadata == proj


# csv_path without mappings raises ValueError.
def test_csv_without_mappings_raises(sensor_csv):
    files = [("frame_001.jpg", T1)]
    with pytest.raises(ValueError, match="mappings"):
        assemble_biigle_records(files, csv_path=sensor_csv)


# mappings without csv_path raises ValueError.
def test_mappings_without_csv_raises(mappings):
    files = [("frame_001.jpg", T1)]
    with pytest.raises(ValueError, match="csv_path"):
        assemble_biigle_records(files, mappings=mappings)


# Naive datetime raises ValueError.
def test_naive_datetime_raises():
    naive = datetime(2025, 6, 1, 12, 0, 0)
    with pytest.raises(ValueError, match="timezone-aware"):
        assemble_biigle_records([("frame_001.jpg", naive)])


# Return type is list of (Path, FrameMetadata) pairs.
def test_return_type():
    from soi_frame_extractor.models.models import FrameMetadata
    files = [("frame_001.jpg", T1)]
    records = assemble_biigle_records(files)
    assert isinstance(records, list)
    path, meta = records[0]
    assert isinstance(path, Path)
    assert isinstance(meta, FrameMetadata)


# Output ordering matches input order (no implicit sort).
def test_order_preserved():
    files = [("c.jpg", T3), ("a.jpg", T1), ("b.jpg", T2)]
    records = assemble_biigle_records(files)
    assert [p.name for p, _ in records] == ["c.jpg", "a.jpg", "b.jpg"]


# Nonexistent csv_path raises FileNotFoundError.
def test_missing_csv_raises(tmp_path, mappings):
    files = [("frame_001.jpg", T1)]
    with pytest.raises(FileNotFoundError):
        assemble_biigle_records(files, csv_path=tmp_path / "nonexistent.csv", mappings=mappings)
