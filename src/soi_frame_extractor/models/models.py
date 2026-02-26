"""Shared data models for soi-frame-extractor.

All core data structures used across the library are defined here.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from numpy.typing import NDArray
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Video input models
# ---------------------------------------------------------------------------

class VideoFile(BaseModel):
    path: Path
    utc_start: datetime
    duration: timedelta | None = None  # populated by video_reader on open


class VideoSession(BaseModel):
    files: list[VideoFile]


# ---------------------------------------------------------------------------
# Frame output models
# ---------------------------------------------------------------------------

class FrameMetadata(BaseModel):
    pass  # fields TBD


@dataclass
class ExtractedFrame:
    frame: NDArray          # (H, W, 3) uint8 RGB
    metadata: FrameMetadata
