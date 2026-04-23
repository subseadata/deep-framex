import pytest
from deep_framex.config.spec_parser import spec_from_dict
from datetime import datetime, timezone


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
