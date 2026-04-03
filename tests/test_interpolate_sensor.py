import pytest
import warnings
from datetime import datetime, timezone
from soi_frame_extractor.planning.planner import _interpolate_sensor
from soi_frame_extractor.db.session_db import create_session_db


# Fixture: in-memory DB with a sensor_readings table and a few rows of depth data.
# Rows are spaced 10 seconds apart starting at 2025-06-01T10:00:00Z (Unix epoch 1748772000.0).
@pytest.fixture
def conn():
    c = create_session_db()
    c.execute("CREATE TABLE sensor_readings (timestamp REAL PRIMARY KEY, depth REAL NOT NULL)")
    c.executemany("INSERT INTO sensor_readings VALUES (?, ?)", [
        (1748772000.0, 100.0),
        (1748772010.0, 120.0),
        (1748772020.0, 140.0),
        (1748772030.0, 160.0),
        (1748772040.0, 180.0),
    ])
    c.commit()
    yield c
    c.close()


# Exact hit, timestamp matches a sensor row exactly, should return that value.
def test_interpolate_exact_match(conn):
    result = _interpolate_sensor(1748772020.0, ["depth"], conn)
    assert result["depth"] == 140.0

# Midpoint, timestamp halfway between two rows, result should be their average.
def test_interpolate_midpoint(conn):
    result = _interpolate_sensor(1748772015.0, ["depth"], conn)
    assert result["depth"] == pytest.approx(130.0)

# extrapolate before data should return nearest value and issue a UserWarning.
def test_interpolate_before_data_warns(conn):
    with pytest.warns(UserWarning):
        result = _interpolate_sensor(1748771990.0, ["depth"], conn)
    assert "depth" in result

# extrapolate after data should return nearest value and issue a UserWarning.
def test_interpolate_before_data_warns(conn):
    with pytest.warns(UserWarning):
        result = _interpolate_sensor(1748772050.0, ["depth"], conn)
    assert "depth" in result

# Empty DB — no rows at all, should return empty dict.
def test_interpolate_empty_db():
    c = create_session_db()
    c.execute("CREATE TABLE sensor_readings (timestamp REAL PRIMARY KEY, depth REAL NOT NULL)")
    c.commit()
    result = _interpolate_sensor(1748772020.00, ["depth"], c)
    assert result == {}
    c.close()
