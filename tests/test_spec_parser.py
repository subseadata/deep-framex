import pytest
from deep_framex.config.spec_parser import spec_from_dict
from datetime import datetime, timedelta, timezone


# Minimum valid input: only rules + interval_s required.
def test_spec_from_dict():
    spec = spec_from_dict({"rules": [{"interval_s": 10.0}]})
    assert len(spec.rules) == 1
    assert spec.rules[0].interval_s == 10.0


# Full-featured spec mirroring test_spec.yaml.
@pytest.fixture
def full_spec():
    return spec_from_dict({
        "rules": [
            {"interval_s": 30.0},
            {
                "interval_s": 10.0,
                "periods": [
                    {"start": "2025-10-15T10:20:00Z", "end": "2025-10-15T10:28:00Z"},
                ],
            },
            {
                "interval_s": 15.0,
                "constraints": [
                    {"column": "depth", "min": 370, "max": 373},
                ],
            },
        ],
        "mappings": {
            "timestamp": "Timestamp",
            "latitude": "Latitude_ddeg",
            "longitude": "Longitude_ddeg",
            "depth": "Depth_m",
            "altitude": "Altitude_m",
            "heading": "HeadingTrue_deg",
            "pitch": "Pitch_deg",
            "roll": "Roll_deg",
        },
        "metadata": {
            "cruise_id": "FKTEST999",
            "dive_id": "S9999",
            "vehicle": "Blobfish",
            "camera_make": "FakeCam",
            "camera_model": "UnderwaterToaster 3000",
            "credit": "Dept of Fictitious Oceanography",
            "source": "ROV Imaginary",
            "copyright": "© 9999 Nobody",
        },
        "initial_offset_s": 5.0,
        "stream_output": False,
        "max_workers": 1,
    })


# All three rules present with correct interval_s; periods/constraints in right rules.
def test_rules_parsed(full_spec):
    assert len(full_spec.rules) == 3
    assert full_spec.rules[0].interval_s == 30.0
    assert len(full_spec.rules[1].periods) == 1
    assert full_spec.rules[1].interval_s == 10.0
    assert len(full_spec.rules[2].constraints) == 1
    assert full_spec.rules[2].interval_s == 15.0


# Period strings must be parsed into timezone-aware datetime objects.
def test_periods_parsed(full_spec):
    assert full_spec.rules[1].periods[0].start == datetime(2025, 10, 15, 10, 20, 0, tzinfo=timezone.utc)
    assert full_spec.rules[1].periods[0].end == datetime(2025, 10, 15, 10, 28, 0, tzinfo=timezone.utc)


# Constraint column name and numeric bounds must survive parsing intact.
def test_constraints_parsed(full_spec):
    assert full_spec.rules[2].constraints[0].column == "depth"
    assert full_spec.rules[2].constraints[0].min == 370
    assert full_spec.rules[2].constraints[0].max == 373


# Mappings is a ColumnMappings model, fields accessed with dot notation.
def test_mappings_parsed(full_spec):
    assert full_spec.mappings.timestamp == "Timestamp"
    assert full_spec.mappings.latitude == "Latitude_ddeg"
    assert full_spec.mappings.longitude == "Longitude_ddeg"
    assert full_spec.mappings.depth == "Depth_m"
    assert full_spec.mappings.altitude == "Altitude_m"
    assert full_spec.mappings.heading == "HeadingTrue_deg"
    assert full_spec.mappings.pitch == "Pitch_deg"
    assert full_spec.mappings.roll == "Roll_deg"


# project_metadata is a plain dict, values accessed with square brackets.
def test_metadata_parsed(full_spec):
    assert full_spec.project_metadata["cruise_id"] == "FKTEST999"
    assert full_spec.project_metadata["dive_id"] == "S9999"
    assert full_spec.project_metadata["vehicle"] == "Blobfish"
    assert full_spec.project_metadata["camera_make"] == "FakeCam"
    assert full_spec.project_metadata["camera_model"] == "UnderwaterToaster 3000"
    assert full_spec.project_metadata["credit"] == "Dept of Fictitious Oceanography"
    assert full_spec.project_metadata["source"] == "ROV Imaginary"
    assert full_spec.project_metadata["copyright"] == "© 9999 Nobody"


# Optional fields parsed correctly.
def test_optional_fields(full_spec):
    assert full_spec.initial_offset_s == 5.0
    assert full_spec.stream_output == False
    assert full_spec.max_workers == 1


# rules key missing or empty, nothing to extract.
def test_missing_rules_raises():
    with pytest.raises(ValueError):
        spec_from_dict({"rules": []})
    with pytest.raises(ValueError):
        spec_from_dict({})


# Rule with no interval_s key.
def test_missing_interval_raises():
    with pytest.raises(ValueError):
        spec_from_dict({"rules": [{}]})


# interval_s must be a positive float.
def test_invalid_interval_raises():
    with pytest.raises(ValueError):
        spec_from_dict({"rules": [{"interval_s": "so many seconds"}]})
    with pytest.raises(ValueError):
        spec_from_dict({"rules": [{"interval_s": -5.0}]})



# Period datetimes must be valid, UTC-aware, and start before end.
def test_invalid_datetime_raises():
    with pytest.raises(ValueError):
        spec_from_dict({"rules": [{"interval_s": 10.0, "periods": [{"start": "not-a-date", "end": "2025-10-15T10:28:00Z"}]}]})
    with pytest.raises(ValueError):
        spec_from_dict({"rules": [{"interval_s": 10.0, "periods": [{"start": "2025-10-15T10:20:00", "end": "2025-10-15T10:28:00"}]}]})
    with pytest.raises(ValueError):
        spec_from_dict({"rules": [{"interval_s": 10.0, "periods": [{"start": "2025-10-15T10:28:00Z", "end": "2025-10-15T10:20:00Z"}]}]})


# mappings block present but missing timestamp key.
def test_missing_mappings_timestamp_raises():
    with pytest.raises(ValueError):
        spec_from_dict({"rules": [{"interval_s": 10.0}], "mappings": {"latitude": "lat"}})


# video_start_times: filename -> ISO 8601 UTC start time override.
def test_video_start_times_parsed():
    spec = spec_from_dict({
        "rules": [{"interval_s": 10.0}],
        "video_start_times": {
            "dive_001.mp4": "2025-11-15T10:00:00Z",
            "dive_002.mp4": "2025-11-15T10:10:00+00:00",
        },
    })
    assert spec.video_start_times["dive_001.mp4"] == datetime(2025, 11, 15, 10, 0, 0, tzinfo=timezone.utc)
    assert spec.video_start_times["dive_002.mp4"] == datetime(2025, 11, 15, 10, 10, 0, tzinfo=timezone.utc)


# video_start_times omitted -> empty dict (no override).
def test_video_start_times_default_empty():
    spec = spec_from_dict({"rules": [{"interval_s": 10.0}]})
    assert spec.video_start_times == {}


# video_start_times value must be a valid ISO 8601 datetime.
def test_video_start_times_invalid_datetime_raises():
    with pytest.raises(ValueError):
        spec_from_dict({"rules": [{"interval_s": 10.0}], "video_start_times": {"a.mp4": "not-a-time"}})


# video_start_times value must be UTC-aware.
def test_video_start_times_naive_datetime_raises():
    with pytest.raises(ValueError):
        spec_from_dict({"rules": [{"interval_s": 10.0}], "video_start_times": {"a.mp4": "2025-11-15T10:00:00"}})


# sensor_time_shift: signed HH:MM:SS string -> timedelta.
def test_sensor_time_shift_parsed():
    spec = spec_from_dict({"rules": [{"interval_s": 10.0}], "sensor_time_shift": "01:30:15"})
    assert spec.sensor_time_shift == timedelta(hours=1, minutes=30, seconds=15)


# A leading '-' makes the shift negative.
def test_sensor_time_shift_negative():
    spec = spec_from_dict({"rules": [{"interval_s": 10.0}], "sensor_time_shift": "-00:00:45"})
    assert spec.sensor_time_shift == timedelta(seconds=-45)


# Both sensor alignment keys omitted -> None (no correction).
def test_sensor_alignment_default_none():
    spec = spec_from_dict({"rules": [{"interval_s": 10.0}]})
    assert spec.sensor_time_shift is None
    assert spec.sensor_start_time is None


# sensor_time_shift must be three colon-separated integers.
def test_sensor_time_shift_invalid_raises():
    with pytest.raises(ValueError):
        spec_from_dict({"rules": [{"interval_s": 10.0}], "sensor_time_shift": "90 minutes"})


# An unquoted HH:MM:SS in YAML reaches the parser as a sexagesimal int — reject it
# rather than silently treating 5400 as a shift.
def test_sensor_time_shift_unquoted_yaml_raises():
    with pytest.raises(ValueError):
        spec_from_dict({"rules": [{"interval_s": 10.0}], "sensor_time_shift": 5400})


# sensor_start_time: ISO 8601 UTC time for the earliest sensor reading.
def test_sensor_start_time_parsed():
    spec = spec_from_dict({"rules": [{"interval_s": 10.0}], "sensor_start_time": "2025-11-15T10:00:00Z"})
    assert spec.sensor_start_time == datetime(2025, 11, 15, 10, 0, 0, tzinfo=timezone.utc)


# sensor_start_time must be UTC-aware.
def test_sensor_start_time_naive_raises():
    with pytest.raises(ValueError):
        spec_from_dict({"rules": [{"interval_s": 10.0}], "sensor_start_time": "2025-11-15T10:00:00"})


# The two alignment keys express conflicting intents — setting both is an error.
def test_sensor_shift_and_start_time_together_raises():
    with pytest.raises(ValueError):
        spec_from_dict({
            "rules": [{"interval_s": 10.0}],
            "sensor_time_shift": "00:01:00",
            "sensor_start_time": "2025-11-15T10:00:00Z",
        })
