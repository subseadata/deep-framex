import csv
import pytest
from datetime import datetime, timezone
from pathlib import Path

from soi_frame_extractor.metadata.biigle import _build_biigle_row, write_biigle_manifest
from soi_frame_extractor.models.models import FrameMetadata


def make_meta(utc, snapshot=None, project_metadata=None):
    return FrameMetadata(
        utc_timestamp=utc,
        video_path=Path("/data/video.mov"),
        offset_s=0.0,
        sensor_snapshot=snapshot or {},
        project_metadata=project_metadata or {},
    )


T1 = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
T2 = datetime(2025, 6, 1, 12, 0, 5, tzinfo=timezone.utc)


# _build_biigle_row — minimal: only filename and taken_at.
def test_build_biigle_row_minimal():
    meta = make_meta(T1)
    row = _build_biigle_row(Path("frame_001.jpg"), meta)
    assert row == {"filename": "frame_001.jpg", "taken_at": "2025-06-01 12:00:00"}


# _build_biigle_row — lat/lng included only when both are present.
def test_build_biigle_row_lat_lng():
    meta = make_meta(T1, snapshot={"latitude": -32.5, "longitude": 151.2})
    row = _build_biigle_row(Path("frame_001.jpg"), meta)
    assert row["lat"] == "-32.5"
    assert row["lng"] == "151.2"


# _build_biigle_row — lat without lng: neither column appears.
def test_build_biigle_row_lat_only():
    meta = make_meta(T1, snapshot={"latitude": -32.5})
    row = _build_biigle_row(Path("frame_001.jpg"), meta)
    assert "lat" not in row
    assert "lng" not in row


# _build_biigle_row — depth converts to negative gps_altitude.
def test_build_biigle_row_depth():
    meta = make_meta(T1, snapshot={"depth": 500.0})
    row = _build_biigle_row(Path("frame_001.jpg"), meta)
    assert row["gps_altitude"] == "-500.0"


# _build_biigle_row — altitude maps to distance_to_ground.
def test_build_biigle_row_altitude():
    meta = make_meta(T1, snapshot={"altitude": 3.5})
    row = _build_biigle_row(Path("frame_001.jpg"), meta)
    assert row["distance_to_ground"] == "3.5"


# _build_biigle_row — heading maps to yaw.
def test_build_biigle_row_heading():
    meta = make_meta(T1, snapshot={"heading": 270.0})
    row = _build_biigle_row(Path("frame_001.jpg"), meta)
    assert row["yaw"] == "270.0"


# _build_biigle_row — full sensor snapshot produces all columns.
def test_build_biigle_row_full():
    snap = {"latitude": -32.5, "longitude": 151.2, "depth": 500.0, "altitude": 3.5, "heading": 90.0}
    meta = make_meta(T1, snapshot=snap)
    row = _build_biigle_row(Path("frame_001.jpg"), meta)
    assert set(row.keys()) == {"filename", "taken_at", "lat", "lng", "gps_altitude", "distance_to_ground", "yaw"}


# write_biigle_manifest — creates file in output_dir named biigle_metadata.csv.
def test_write_biigle_manifest_creates_file(tmp_path):
    written = [
        (tmp_path / "frame_001.jpg", make_meta(T1)),
        (tmp_path / "frame_002.jpg", make_meta(T2)),
    ]
    result = write_biigle_manifest(written, tmp_path)
    assert result == tmp_path / "biigle_metadata.csv"
    assert result.exists()


# write_biigle_manifest — rows are sorted by timestamp regardless of input order.
def test_write_biigle_manifest_sorted(tmp_path):
    written = [
        (tmp_path / "frame_002.jpg", make_meta(T2)),
        (tmp_path / "frame_001.jpg", make_meta(T1)),
    ]
    result = write_biigle_manifest(written, tmp_path)
    rows = list(csv.DictReader(result.open()))
    assert rows[0]["filename"] == "frame_001.jpg"
    assert rows[1]["filename"] == "frame_002.jpg"


# write_biigle_manifest — columns limited to those actually present in data.
def test_write_biigle_manifest_minimal_columns(tmp_path):
    written = [(tmp_path / "frame_001.jpg", make_meta(T1))]
    result = write_biigle_manifest(written, tmp_path)
    rows = list(csv.DictReader(result.open()))
    assert set(rows[0].keys()) == {"filename", "taken_at"}


# write_biigle_manifest — optional columns appear when data has them.
def test_write_biigle_manifest_with_sensor(tmp_path):
    snap = {"latitude": -32.5, "longitude": 151.2, "depth": 100.0}
    written = [(tmp_path / "frame_001.jpg", make_meta(T1, snapshot=snap))]
    result = write_biigle_manifest(written, tmp_path)
    rows = list(csv.DictReader(result.open()))
    assert "lat" in rows[0]
    assert "lng" in rows[0]
    assert "gps_altitude" in rows[0]
    assert rows[0]["gps_altitude"] == "-100.0"


# write_biigle_manifest — column order follows BIIGLE spec (filename, taken_at, lat, lng, ...).
def test_write_biigle_manifest_column_order(tmp_path):
    snap = {"latitude": -32.5, "longitude": 151.2, "depth": 100.0, "altitude": 3.0, "heading": 45.0}
    written = [(tmp_path / "frame_001.jpg", make_meta(T1, snapshot=snap))]
    result = write_biigle_manifest(written, tmp_path)
    with result.open() as f:
        header = f.readline().strip().split(",")
    assert header == ["filename", "taken_at", "lat", "lng", "gps_altitude", "distance_to_ground", "yaw"]


# write_biigle_manifest — returns the path to the written file.
def test_write_biigle_manifest_returns_path(tmp_path):
    written = [(tmp_path / "frame_001.jpg", make_meta(T1))]
    result = write_biigle_manifest(written, tmp_path)
    assert isinstance(result, Path)
