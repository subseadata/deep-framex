from deep_framex.planning.planner import _intersect_windows, _sample_timestamps
from deep_framex.models.core import TimePeriod
from datetime import datetime, timezone

def test_intersect_windows():
    # Test intersecting time periods
    assert _intersect_windows([TimePeriod(start=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
                  end=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc))],
      [TimePeriod(start=datetime(2025, 1, 1, 10, 5, tzinfo=timezone.utc),
                  end=datetime(2025, 1, 1, 10, 15, tzinfo=timezone.utc))],
    ) == [TimePeriod(start=datetime(2025, 1, 1, 10, 5, tzinfo=timezone.utc),
                    end=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc))]
    
    # Test non-intersecting time periods
    assert _intersect_windows([TimePeriod(start=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
                  end=datetime(2025, 1, 1, 10, 5, tzinfo=timezone.utc))],
      [TimePeriod(start=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc),
                  end=datetime(2025, 1, 1, 10, 15, tzinfo=timezone.utc))],
    ) == []
    
    # Test time period within time period
    assert _intersect_windows([TimePeriod(start=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
                  end=datetime(2025, 1, 1, 10, 20, tzinfo=timezone.utc))],
      [TimePeriod(start=datetime(2025, 1, 1, 10, 5, tzinfo=timezone.utc),
                  end=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc))],
    ) == [TimePeriod(start=datetime(2025, 1, 1, 10, 5, tzinfo=timezone.utc),
                    end=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc))]
    
    # Test single touching point
    assert _intersect_windows([TimePeriod(start=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
                  end=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc))],
      [TimePeriod(start=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc),
                  end=datetime(2025, 1, 1, 10, 15, tzinfo=timezone.utc))],
    ) == [TimePeriod(start=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc),
                    end=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc))]
 
def test_sample_timestamps():
    # Test should return one timestamp for zero duration
    assert _sample_timestamps([TimePeriod(start=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
                              end=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc))], 30.0,
                              datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), 0.0,
                              ) == [datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)]

    # Offset and interval should yield two datetimes here
    assert _sample_timestamps([TimePeriod(start=datetime(2025, 1, 1, 10, 9, tzinfo=timezone.utc),
                              end=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc))], 30.0,
                              datetime(2025, 1, 1, 10, 9, tzinfo=timezone.utc), 10.0,
                              ) == [datetime(2025, 1, 1, 10, 9, 10, tzinfo=timezone.utc),
                                 datetime(2025, 1, 1, 10, 9, 40, tzinfo=timezone.utc)]

    # Empty list should return []
    assert _sample_timestamps([], 30.0,
                              datetime(2025, 1, 1, 10, 9, tzinfo=timezone.utc), 10.0,
                              ) == []

    # Offset and interval should yield two datetimes here
    assert _sample_timestamps([TimePeriod(start=datetime(2025, 1, 1, 10, 9, tzinfo=timezone.utc),
                              end=datetime(2025, 1, 1, 10, 10, tzinfo=timezone.utc))], 30.0,
                              datetime(2025, 1, 1, 10, 9, tzinfo=timezone.utc), 5000.0,
                              ) == []




# --- multi-source planning -------------------------------------------------

import pytest
import sqlite3
from datetime import timedelta
from pathlib import Path

from deep_framex.config.spec_parser import spec_from_dict
from deep_framex.data.importer import import_csv
from deep_framex.db.session_db import create_session_db
from deep_framex.models.core import SensorSource, VideoFile, VideoSession
from deep_framex.planning.planner import interpolate_sensor, plan, sensor_columns


# Fixture: fresh in-memory DB for each test.
@pytest.fixture
def conn():
    c = create_session_db()
    yield c
    c.close()


# Fixture: a one-minute session. plan() never opens the file, so the path
# need not exist.
@pytest.fixture
def session():
    return VideoSession(videos=[VideoFile(
        path=Path("dive.mp4"),
        utc_start=datetime(2025, 10, 15, 10, 0, 0, tzinfo=timezone.utc),
        duration=timedelta(seconds=60),
    )])


# Fixture: two sensor files on different grids with disjoint columns. Both run
# past the end of the video so no frame needs extrapolating.
#
# The CTD logs every 7 s, so frames land between its readings, and every third
# reading carries a +50 spike — the erratic reading the interpolation window
# exists to smooth, which is what makes the window size observable. The nav
# logs every 15 s and rises linearly, so its values do not depend on the
# window at all.
@pytest.fixture
def two_csvs(tmp_path):
    def rows(header, step, value):
        base = datetime(2025, 10, 15, 10, 0, 0, tzinfo=timezone.utc)
        return f"utc_time,{header}\n" + "".join(
            f"{(base + timedelta(seconds=s)):%Y-%m-%dT%H:%M:%SZ},{value(s)}\n"
            for s in range(0, 75, step)
        )

    def ctd_value(s):
        spike = 50 if (s // 7) % 3 == 1 else 0
        return f"{100 + s + spike},{2.0 + s / 100}"

    ctd = tmp_path / "ctd.csv"
    ctd.write_text(rows("Depth_m,Temp_C", 7, ctd_value))
    nav = tmp_path / "nav.csv"
    nav.write_text(rows("Lat", 15, lambda s: 27.0 + s / 1000))
    return ctd, nav


# Load every source the way the pipeline does, and return the spec.
def _load(conn, raw):
    spec = spec_from_dict(raw)
    for i, source in enumerate(spec.sensors):
        import_csv(source.file, conn, source, source.time_shift, source.start_time,
                   f"sensor_readings_{i}")
    return spec


# Fixture: a spec naming both files, ready to plan.
@pytest.fixture
def two_source_raw(two_csvs):
    ctd, nav = two_csvs
    return {
        "rules": [{"interval_s": 30.0}],
        "sensors": [
            {"file": str(ctd), "timestamp": "utc_time", "depth": "Depth_m",
             "temperature": "Temp_C"},
            {"file": str(nav), "timestamp": "utc_time", "latitude": "Lat"},
        ],
    }


# Every frame carries values from both files, each interpolated on its own grid.
def test_snapshot_merges_both_sources(conn, session, two_source_raw):
    spec = _load(conn, two_source_raw)
    plans = plan(spec, session, conn)
    frames = plans[0].frames
    assert frames
    for frame in frames:
        assert set(frame.sensor_snapshot) == {"depth", "temperature", "latitude"}


# With no sensors at all the snapshot is empty rather than absent.
def test_no_sources_gives_empty_snapshots(conn, session):
    spec = spec_from_dict({"rules": [{"interval_s": 30.0}]})
    plans = plan(spec, session, conn)
    assert all(f.sensor_snapshot == {} for f in plans[0].frames)


# A constraint is resolved against whichever file supplied its column, so a
# bound on the nav file's latitude narrows the plan.
def test_constraint_resolves_against_its_own_source(conn, session, two_source_raw):
    two_source_raw["rules"] = [{
        "interval_s": 10.0,
        "constraints": [{"column": "latitude", "min": 27.03}],
    }]
    spec = _load(conn, two_source_raw)
    plans = plan(spec, session, conn)
    utcs = [session.videos[0].utc_start + timedelta(seconds=f.offset_s)
            for f in plans[0].frames]
    # Nav readings at or above 27.03 start at 10:00:30.
    assert min(utcs) >= datetime(2025, 10, 15, 10, 0, 30, tzinfo=timezone.utc)


# A constraint naming a column no file supplied lists the union of what is
# available, not just one file's columns.
def test_constraint_on_unknown_column_lists_all_sources(conn, session, two_source_raw):
    two_source_raw["rules"] = [{
        "interval_s": 30.0,
        "constraints": [{"column": "salinity"}],
    }]
    spec = _load(conn, two_source_raw)
    with pytest.raises(ValueError) as excinfo:
        plan(spec, session, conn)
    message = str(excinfo.value)
    assert "salinity" in message
    for column in ("depth", "temperature", "latitude"):
        assert column in message


# A constraint with no sensor data imported at all is a clearer error than a
# missing-table crash.
def test_constraint_without_any_sensor_data_raises(conn, session):
    spec = spec_from_dict({
        "rules": [{"interval_s": 30.0, "constraints": [{"column": "depth"}]}],
    })
    with pytest.raises(ValueError, match="no CSV was imported"):
        plan(spec, session, conn)


# Each source interpolates at its own window: changing one entry's window
# moves that file's values and leaves the other file's untouched.
def test_interpolation_window_is_per_source(conn, session, two_source_raw):
    base = _load(conn, two_source_raw)
    base_frames = plan(base, session, conn)[0].frames

    two_source_raw["sensors"][0]["interpolation_window"] = 1
    other = create_session_db()
    try:
        widened = _load(other, two_source_raw)
        widened_frames = plan(widened, session, other)[0].frames
    finally:
        other.close()

    assert [f.sensor_snapshot["latitude"] for f in base_frames] == \
           [f.sensor_snapshot["latitude"] for f in widened_frames]
    assert [f.sensor_snapshot["depth"] for f in base_frames] != \
           [f.sensor_snapshot["depth"] for f in widened_frames]


# An entry that omits interpolation_window uses the spec-level value, not a
# hardcoded default.
def test_spec_level_window_reaches_sources_that_omit_it(conn, session, two_source_raw):
    two_source_raw["interpolation_window"] = 1
    narrow = _load(conn, two_source_raw)
    narrow_frames = plan(narrow, session, conn)[0].frames

    del two_source_raw["interpolation_window"]
    other = create_session_db()
    try:
        default = _load(other, two_source_raw)
        default_frames = plan(default, session, other)[0].frames
    finally:
        other.close()

    assert [f.sensor_snapshot["depth"] for f in narrow_frames] != \
           [f.sensor_snapshot["depth"] for f in default_frames]


# A single mappings block plus --data is normalised into a one-entry sensors
# list carrying the same mappings and the spec-level alignment keys, so the
# shorthand and an explicit one-entry block plan identically.
def test_legacy_shorthand_normalises_to_one_entry(two_csvs):
    ctd, _ = two_csvs
    spec = spec_from_dict({
        "rules": [{"interval_s": 30.0}],
        "mappings": {"timestamp": "utc_time", "depth": "Depth_m", "temperature": "Temp_C"},
        "sensor_time_shift": "-00:03:00",
    })
    source = SensorSource(
        file=ctd,
        time_shift=spec.sensor_time_shift,
        start_time=spec.sensor_start_time,
        **spec.mappings.model_dump(exclude_none=True),
    )
    assert source.file == ctd
    assert source.timestamp == "utc_time"
    assert source.depth == "Depth_m"
    assert source.model_extra == {"temperature": "Temp_C"}
    assert source.time_shift == timedelta(minutes=-3)
    # Not a mapped column, so it must not become a sensor column.
    assert "time_shift" not in (source.model_extra or {})


# sensor_columns reads whichever table it is given, and reports an absent one
# as empty rather than raising.
def test_sensor_columns_per_table(conn, two_source_raw):
    _load(conn, two_source_raw)
    assert sensor_columns(conn, "sensor_readings_0") == ["depth", "temperature"]
    assert sensor_columns(conn, "sensor_readings_1") == ["latitude"]
    assert sensor_columns(conn, "sensor_readings_2") == []


# interpolate_sensor targets the table it is told to, not a fixed name.
def test_interpolate_sensor_targets_given_table(conn, two_source_raw):
    _load(conn, two_source_raw)
    ts = datetime(2025, 10, 15, 10, 0, 25, tzinfo=timezone.utc).timestamp()
    assert set(interpolate_sensor(ts, ["depth"], conn, 2, "sensor_readings_0")) == {"depth"}
    assert set(interpolate_sensor(ts, ["latitude"], conn, 2, "sensor_readings_1")) == {"latitude"}
    with pytest.raises(sqlite3.OperationalError):
        interpolate_sensor(ts, ["depth"], conn, 2, "sensor_readings_9")
