import pytest
from datetime import datetime, timezone
from pathlib import Path
from deep_framex.output.output_frames import validate_filename_template, _render_filename
from deep_framex.models.core import ExtractedFrame, FrameMetadata
import numpy as np


# Fixture: minimal ExtractedFrame for _render_filename tests.
@pytest.fixture
def frame():
    meta = FrameMetadata(
        utc_timestamp=datetime(2025, 10, 15, 10, 25, 18, tzinfo=timezone.utc),
        video_path=Path("/data/video.mov"),
        offset_s=30.0,
        sensor_snapshot={"depth": 371.2, "latitude": -32.5},
        project_metadata={"dive_id": "S9999", "cruise_id": "FKTEST999"},
    )
    return ExtractedFrame(frame=np.zeros((100, 100, 3), dtype=np.uint8), metadata=meta)


# validate_filename_template, all builtin keys.
def test_validate_filename_template():
    validate_filename_template("{utc}_{video_stem}.jpg", [], [])

# validate_filename_template, sensor and metadata keys accepted.
def test_valid_filename_template_sensor_and_metadata_keys():
    validate_filename_template("{utc}_{cruise_id}_{dive_id}_{depth}m_{video_stem}.jpg",
                               ["depth"], ["cruise_id", "dive_id"])

# validate_filename_template, unknown key raises with did-you-mean hint.
def test_validate_filename_template_unknown_key():
    with pytest.raises(ValueError):
        validate_filename_template("{utc}_{cruise_id}_{dive_id}_{dopth}m_{video_stem}.jpg",
                               ["depth"], ["cruise_id", "dive_id"])

# validate_filename_template, invalid format syntax raises.
def test_validate_filename_invalid_syntax():
     with pytest.raises(ValueError):
        validate_filename_template("{utc_{cruise_id}_{dive_id}_{depth}m_{video_stem}.jpg",
                               ["depth"], ["cruise_id", "dive_id"])

# _render_filename, None template uses default pattern.
def test_render_filename_default(frame):
    assert _render_filename(frame, None) == "20251015T102518000000_video.jpg"

# _render_filename, template renders correctly with known keys.
def test_render_filename_basic(frame):
    assert (_render_filename(frame, "{utc}_{cruise_id}_{dive_id}_{depth}m_{video_stem}.jpg")
                            == "20251015T102518000000_FKTEST999_S9999_371.2m_video.jpg")

# _render_filename, bad key in template falls back to default silently.
def test_render_filename_fallback(frame):
    assert (_render_filename(frame, "{utc}_{banana}_{dive_id}_{depth}m_{video_stem}.jpg")
                            == "20251015T102518000000_video.jpg")
