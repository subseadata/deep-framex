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
    """Tells the tool which CSV columns to read and what to call them.

    Each entry pairs the name the tool will use (the field name) with the
    exact column header from the user's CSV file (the value).  For example:

        ColumnMappings(timestamp="Timestamp", depth="Depth_m", latitude="Latitude_ddeg")

    means: read the column called "Depth_m" from the CSV and refer to it as
    "depth" everywhere in the tool — in constraint rules, filename templates,
    and metadata output.

    timestamp is required — the user must always say which CSV column holds
    the time reference.  latitude, longitude, and depth are optional named
    fields; using these exact names triggers automatic routing to EXIF GPS
    tags and iFDO manifest fields.  Any additional entries the user supplies
    (e.g. temperature, salinity) are accepted and written to XMP.
    """

    model_config = ConfigDict(extra='allow')

    timestamp: str                          # required — CSV column name for the UTC timestamp
    latitude: str | None = None             # CSV column name for latitude (decimal degrees)
    longitude: str | None = None            # CSV column name for longitude (decimal degrees)
    depth: str | None = None                # CSV column name for depth (metres, positive)


class ImportedDataset(CustomBaseModel):
    """Describes the sensor data written into the session database.

    Returned by the data importer after loading a CSV into sensor_readings.
    Carries enough information for the planner to validate constraints and
    for the metadata writer to know which canonical fields are resolvable.
    The actual data lives in the session database, not in this model.

    columns holds the canonical names (the keys from ColumnMappings) that
    were imported — these are the DB column names in sensor_readings.
    timestamp_column records the original CSV column name that was used as
    the timestamp source; in the DB it is always stored as 'timestamp'.
    """
    columns: list[str]          # canonical sensor column names in the DB, excluding timestamp
    timestamp_column: str       # original CSV column name used as the timestamp source
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
    initial_offset_s: float = 0.0                   # shift the sampling grid this many seconds from session start
    interpolation_window: int = 2                   # number of sensor rows to use on each side when interpolating
    stream_output: bool = False                     # write each frame to disk immediately instead of buffering per video
    max_workers: int = 1                            # worker processes for extraction; 1 = sequential, >1 = parallel


class FrameSpec(CustomBaseModel):
    """One planned frame: the offset to seek to and the sensor values at that moment.

    Keeping offset and snapshot together means they can never get out of sync,
    and the plan object is self-contained — no database needed at extraction time.
    """
    offset_s: float                     # seconds from t=0 in the source video
    sensor_snapshot: dict[str, float] = {}  # interpolated sensor values at this timestamp


class VideoExtractionPlan(CustomBaseModel):
    video_file: VideoFile
    frames: list[FrameSpec]             # planned frames in ascending offset order
    project_metadata: dict[str, str] = {}  # passed through to every frame's metadata
    # NOTE: video_file.path must be resolvable on whatever machine runs decode_frames.
    # For distributed workers this means a shared filesystem, pre-staged local copy,
    # or (future) a URL string — see open_video in video_reader.py.


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
    is handled separately in metadata/ifdo.py.
    """
    exif: str | None = None
    iptc: str | None = None
    xmp: str | None = None


# Maps canonical field names to their prescribed metadata destinations.
# Fields in this registry are written to the listed layer(s) and are NOT
# duplicated in the XMP custom namespace.  Fields absent from this registry
# fall through to XMP automatically.
#
# iFDO routing is not represented here — iFDO is a standalone JSON sidecar
# written once per run by metadata/ifdo.py, not embedded per-image.
FIELD_REGISTRY: dict[str, MetadataDestination] = {
    # Sensor fields written to EXIF GPS tags
    "latitude":     MetadataDestination(exif="GPSLatitude"),
    "longitude":    MetadataDestination(exif="GPSLongitude"),
    "depth":        MetadataDestination(exif="GPSAltitude"),
    # Project metadata fields written to IPTC
    "credit":       MetadataDestination(iptc="Credit"),
    "source":       MetadataDestination(iptc="Source"),
    "copyright":    MetadataDestination(iptc="CopyrightNotice"),
    "caption":      MetadataDestination(iptc="Caption-Abstract"),
    # Project metadata fields written to EXIF
    "camera_make":  MetadataDestination(exif="Make"),
    "camera_model": MetadataDestination(exif="Model"),
}
