import pytest
from deep_framex.config.timestamp_discovery import parse_filename
from datetime import datetime, timedelta

# Separator mode
def test_separator_parses_timestamp():
    result = parse_filename(
        filename="dive_20251115T102530_FullHD.mp4",
        mode="separator",
        format="%Y%m%dT%H%M%S",
        separator="_",
        group_number=2,
    )

    assert result.error == ''
    assert result.extracted == "20251115T102530"
    assert result.parsed == datetime(2025, 11, 15, 10, 25, 30)

# Range mode
def test_range_parses_timestamp():
    filename = "dive01_2025.11.15_10.25.30-FullHD.mp4"

    result = parse_filename(
        filename=filename,
        mode="range",
        format="%Y.%m.%d_%H.%M.%S",
        start_char=8,
        end_char=26,
    )

    assert result.error == ''
    assert result.extracted == "2025.11.15_10.25.30"
    assert result.parsed == datetime(2025, 11, 15, 10, 25, 30)


def test_range_start_character_one_with_microseconds():
    result = parse_filename(
        filename="20251115T102530123.mp4",
        mode="range",
        format="%Y%m%dT%H%M%S%f",
        start_char=1,
        end_char=18,
    )

    assert result.error == ''
    assert result.extracted == "20251115T102530123"
    assert result.parsed == datetime(2025, 11, 15, 10, 25, 30, 123000)

# Regex mode
def test_regex_parses_timestamp():
    result = parse_filename(
        filename="dive1_20251115T102530-FullHD.mp4",
        mode="regex",
        format="%Y%m%dT%H%M%S",
        regex=r"_(.*?)-",
    )

    assert result.error == ''
    assert result.extracted == "20251115T102530"
    assert result.parsed == datetime(2025, 11, 15, 10, 25, 30)

# Offset tests
def test_regex_parses_timestamp_with_offset_and_microseconds():
    result = parse_filename(
        filename="dive1_20251115T102530123456-FullHD.mp4",
        mode="regex",
        format="%Y%m%dT%H%M%S%f",
        regex=r"_(.*?)-",
        offset=timedelta(minutes=30),
    )

    assert result.error == ''
    assert result.extracted == "20251115T102530123456"
    assert result.parsed == datetime(
        2025, 11, 15, 10, 55, 30, 123456
    )


def test_zero_offset_does_not_change_timestamp():
    result = parse_filename(
        filename="dive_20251115T102530_FullHD.mp4",
        mode="separator",
        format="%Y%m%dT%H%M%S",
        separator="_",
        group_number=2,
        offset=timedelta(0),
    )

    assert result.error == ''
    assert result.parsed == datetime(2025, 11, 15, 10, 25, 30)
