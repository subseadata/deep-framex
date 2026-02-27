"""Shared data models for soi-frame-extractor.

All core data structures used across the library are defined here.
"""

from datetime import datetime, timedelta
from pathlib import Path
import av
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict

# TODO: add @field_validator for arbitrary types once dependencies are installed:
#   - Video.container (av.container.InputContainer) — check open, has video stream
#   - ExtractedFrame.frame (NDArray) — check ndim==3, shape[2]==3, dtype==uint8


class CustomBaseModel(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
    )


# ---------------------------------------------------------------------------
# Video input models
# ---------------------------------------------------------------------------

class VideoFile(CustomBaseModel):
    path: Path
    utc_start: datetime
    duration: timedelta | None = None  # populated by video_reader on open


class Video(CustomBaseModel):
    file: VideoFile
    container: av.container.InputContainer


class VideoSession(CustomBaseModel):
    videos: list[VideoFile]             # ordered by utc_start


# ---------------------------------------------------------------------------
# Extraction planning models
# ---------------------------------------------------------------------------

class TimePeriod(CustomBaseModel):
    start: datetime
    end: datetime


class ExtractionRule(CustomBaseModel):
    interval_s: float
    periods: list[TimePeriod] = []      # if empty, rule applies to full session


class ExtractionSpec(CustomBaseModel):
    rules: list[ExtractionRule]


class VideoExtractionPlan(CustomBaseModel):
    video_file: VideoFile
    offsets_s: list[float]              # seconds from t=0, sorted ascending


# ---------------------------------------------------------------------------
# Frame output models
# ---------------------------------------------------------------------------

class FrameMetadata(CustomBaseModel):
    pass  # fields TBD


class ExtractedFrame(CustomBaseModel):
    frame: NDArray                      # (H, W, 3) uint8 RGB
    metadata: FrameMetadata
