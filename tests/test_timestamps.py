import pytest
from datetime import datetime, timezone
from pathlib import Path

from soi_frame_extractor.utils.timestamps import (
    _template_to_regex,
    _parse_utc_string,
    parse_filename_template,
    parse_file_list_csv,
)


# ---------------------------------------------------------------------------
# _parse_utc_string
# ---------------------------------------------------------------------------

def test_parse_utc_microseconds():
    dt = _parse_utc_string("20251115T102530123456")
    assert dt == datetime(2025, 11, 15, 10, 25, 30, 123456, tzinfo=timezone.utc)

def test_parse_utc_milliseconds():
    dt = _parse_utc_string("20251115T102530123")
    assert dt == datetime(2025, 11, 15, 10, 25, 30, 123000, tzinfo=timezone.utc)

def test_parse_utc_seconds_only():
    dt = _parse_utc_string("20251115T102530")
    assert dt == datetime(2025, 11, 15, 10, 25, 30, tzinfo=timezone.utc)

def test_parse_utc_invalid_raises():
    with pytest.raises(ValueError):
        _parse_utc_string("not-a-timestamp")


# ---------------------------------------------------------------------------
# _template_to_regex
# ---------------------------------------------------------------------------

def test_template_to_regex_bare_utc():
    pat = _template_to_regex("{utc}.jpg")
    assert pat.match("20251115T102530123456")

def test_template_to_regex_prefix_and_utc():
    pat = _template_to_regex("{dive_id}_{utc}.jpg")
    assert pat.match("D001_20251115T102530123456")

def test_template_to_regex_no_utc_raises():
    with pytest.raises(ValueError, match="utc"):
        _template_to_regex("{dive_id}_{video_stem}.jpg")

# Regression: format specs like {offset_s:.1f} must be tokenised correctly,
# not escaped as literal text.
def test_template_to_regex_format_spec():
    pat = _template_to_regex("{utc}_{offset_s:.1f}s.jpg")
    assert pat.match("20251115T102530123456_30.0s")

def test_template_to_regex_format_spec_no_match_on_mismatch():
    pat = _template_to_regex("{utc}_{offset_s:.1f}s.jpg")
    assert pat.match("20251115T102530123456_WRONG") is None

def test_template_to_regex_utc_group_captured():
    pat = _template_to_regex("{dive_id}_{utc}_{offset_s:.1f}s.jpg")
    m = pat.match("D001_20251115T102530123456_30.0s")
    assert m is not None
    assert m.group("utc") == "20251115T102530123456"

# Regression: duplicate placeholder names must not raise re.error.
def test_template_to_regex_duplicate_placeholder():
    pat = _template_to_regex("{dive_id}_{dive_id}_{utc}.jpg")
    m = pat.match("D001_D001_20251115T102530123456")
    assert m is not None
    assert m.group("utc") == "20251115T102530123456"


# ---------------------------------------------------------------------------
# parse_filename_template
# ---------------------------------------------------------------------------

def test_parse_filename_template_basic():
    dt = parse_filename_template(Path("D001_20251115T102530123456.jpg"), "{dive_id}_{utc}")
    assert dt == datetime(2025, 11, 15, 10, 25, 30, 123456, tzinfo=timezone.utc)

def test_parse_filename_template_no_extension_in_template():
    dt = parse_filename_template(Path("20251115T102530123456.jpg"), "{utc}")
    assert dt == datetime(2025, 11, 15, 10, 25, 30, 123456, tzinfo=timezone.utc)

def test_parse_filename_template_with_format_spec():
    # Round-trip: template with format spec matches filenames produced by that template.
    dt = parse_filename_template(
        Path("20251115T102530123456_30.0s.jpg"),
        "{utc}_{offset_s:.1f}s.jpg",
    )
    assert dt == datetime(2025, 11, 15, 10, 25, 30, 123456, tzinfo=timezone.utc)

def test_parse_filename_template_no_match_raises():
    with pytest.raises(ValueError, match="does not match"):
        parse_filename_template(Path("unrelated_name.jpg"), "{dive_id}_{utc}.jpg")

def test_parse_filename_template_no_utc_raises():
    with pytest.raises(ValueError, match="utc"):
        parse_filename_template(Path("frame.jpg"), "{dive_id}_{video_stem}.jpg")

def test_parse_filename_template_result_is_utc_aware():
    dt = parse_filename_template(Path("20251115T102530123456.jpg"), "{utc}")
    assert dt.tzinfo is timezone.utc


# ---------------------------------------------------------------------------
# parse_file_list_csv
# ---------------------------------------------------------------------------

@pytest.fixture
def file_list_csv(tmp_path):
    p = tmp_path / "files.csv"
    p.write_text(
        "filename,timestamp\n"
        "image001.jpg,2023-12-01T14:30:22.456Z\n"
        "image002.jpg,2023-12-01T14:30:25.102Z\n"
    )
    return p

def test_parse_file_list_csv_basic(file_list_csv):
    result = parse_file_list_csv(file_list_csv)
    assert len(result) == 2
    assert result[0][0] == "image001.jpg"
    assert result[0][1] == datetime(2023, 12, 1, 14, 30, 22, 456000, tzinfo=timezone.utc)

def test_parse_file_list_csv_result_is_utc_aware(file_list_csv):
    result = parse_file_list_csv(file_list_csv)
    for _, dt in result:
        assert dt.tzinfo is not None

def test_parse_file_list_csv_naive_timestamp_assumed_utc(tmp_path):
    p = tmp_path / "files.csv"
    p.write_text("filename,timestamp\nimage001.jpg,2023-12-01T14:30:22\n")
    result = parse_file_list_csv(p)
    assert result[0][1].tzinfo is timezone.utc

def test_parse_file_list_csv_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_file_list_csv(tmp_path / "nonexistent.csv")

def test_parse_file_list_csv_missing_column_raises(file_list_csv):
    with pytest.raises(KeyError):
        parse_file_list_csv(file_list_csv, filename_col="wrong_col")

def test_parse_file_list_csv_custom_columns(tmp_path):
    p = tmp_path / "files.csv"
    p.write_text("name,time\nimage001.jpg,2023-12-01T14:30:22Z\n")
    result = parse_file_list_csv(p, filename_col="name", timestamp_col="time")
    assert result[0][0] == "image001.jpg"
