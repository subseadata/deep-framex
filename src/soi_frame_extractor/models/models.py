"""Shared data models for soi-frame-extractor.

All core data structures used across the library are defined here.
"""

from datetime import datetime, timedelta
from pathlib import Path

import av
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

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
    duration: timedelta


class Video(CustomBaseModel):
    file: VideoFile
    container: av.container.InputContainer


class VideoSession(CustomBaseModel):
    videos: list[VideoFile]             # ordered by utc_start


# ---------------------------------------------------------------------------
# Sensor data models
# ---------------------------------------------------------------------------

class ColumnMappings(CustomBaseModel):
    """Maps user CSV column names to canonical metadata field names.

    timestamp is required — the user must always name which CSV column holds
    the time reference.  latitude, longitude, and depth are optional — if
    none are provided, extracted frames will carry no location metadata.
    Any additional mappings the user supplies (e.g. temp, salinity) are
    accepted as extra fields and written to XMP under their key name.

    Keys are the canonical names used in metadata output.
    Values are the exact column names as they appear in the user's CSV.
    """
    model_config = ConfigDict(extra='allow')

    timestamp: str                          # required — name of the timestamp column in the CSV
    latitude: str | None = None
    longitude: str | None = None
    depth: str | None = None


class ImportedDataset(CustomBaseModel):
    """Describes the sensor data written into the session database.

    Returned by the data importer after loading a CSV into sensor_readings.
    Carries enough information for the planner to validate constraints and
    for the metadata writer to know which canonical fields are resolvable.
    The actual data lives in the session database, not in this model.
    """
    columns: list[str]          # sensor column names, excluding timestamp
    timestamp_column: str       # name of the timestamp column in the CSV
    row_count: int
    utc_start: datetime
    utc_end: datetime


# ---------------------------------------------------------------------------
# Extraction planning models
# ---------------------------------------------------------------------------

class TimePeriod(CustomBaseModel):
    start: datetime
    end: datetime


class ExtractionRule(CustomBaseModel):

    class SensorConstraint(CustomBaseModel):
        """A min/max bound applied to a single sensor column during planning.

        Restricts this rule's frames to readings within an environmental
        range (e.g., depth between 1000 and 1200 m).  Either bound may be
        omitted to produce a one-sided constraint.

        column must match a column name present in the imported CSV.
        """
        column: str
        min: float | None = None
        max: float | None = None

    interval_s: float
    periods: list[TimePeriod] = Field(default_factory=list)         # if empty, rule applies to full session
    constraints: list[SensorConstraint] = Field(default_factory=list)


class ExtractionSpec(CustomBaseModel):
    rules: list[ExtractionRule]
    mappings: ColumnMappings | None = None          # omit if no CSV was imported
    project_metadata: dict[str, str] = {}
    xmp_namespace_uri: str = "https://soi-frame-extractor.org/xmp/v1/"
    xmp_namespace_prefix: str = "sfe"
    filename_template: str | None = None            # omit to use default naming
    stream_output: bool = False                     # write each frame to disk immediately instead of buffering per video


class VideoExtractionPlan(CustomBaseModel):
    video_file: VideoFile
    offsets_s: list[float]              # seconds from t=0, sorted ascending


# ---------------------------------------------------------------------------
# Frame output models
# ---------------------------------------------------------------------------

class FrameMetadata(CustomBaseModel):
    """All metadata associated with a single extracted frame.

    sensor_snapshot holds interpolated sensor values at the frame's exact
    timestamp, keyed by canonical name (the left-hand side of the mappings
    block in the YAML spec — e.g. "depth", "latitude", not the original CSV
    column names).  The planner performs this remapping when building the
    snapshot.  project_metadata carries the operator-supplied fields from the
    YAML spec.  Both travel with the frame through the pipeline and are
    written into the image file by the metadata writer.
    """
    utc_timestamp: datetime
    video_path: Path
    offset_s: float
    sensor_snapshot: dict[str, float] = {}
    project_metadata: dict[str, str] = {}


class ExtractedFrame(CustomBaseModel):
    frame: NDArray                      # (H, W, 3) uint8 RGB
    metadata: FrameMetadata


# ---------------------------------------------------------------------------
# Metadata routing
# ---------------------------------------------------------------------------

class MetadataDestination(CustomBaseModel):
    """Prescribed metadata layer destinations for a canonical field.

    Describes which tag or property name to use in each metadata standard.
    A None value for a layer means the field is not written there.
    Tag and property names follow the conventions of each standard and are
    resolved by the metadata writer at write time.

    iFDO is not represented here — it is written as a standalone JSON sidecar
    file for the whole image set, not embedded per-image.  iFDO field routing
    is handled separately in output/ifdo.py.
    """
    exif: str | None = None
    iptc: str | None = None
    xmp: str | None = None


# Maps canonical field names to their prescribed metadata destinations.
# The metadata writer consults this to route known fields to the correct
# layer and tag.  Anything not in this registry goes to XMP under its
# original column name.  Populated at implementation time once tag
# references are confirmed against each standard.
FIELD_REGISTRY: dict[str, MetadataDestination] = {}
