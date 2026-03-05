"""Pipeline orchestrator

Top-level function that wires all pipeline stages together and drives an
extraction run from a YAML spec to annotated image files on disk.

Stage order:
    1. Parse spec from YAML
    2. Discover and probe video files
    3. Assemble VideoSession (sorted by utc_start)
    4. Initialise session database (in-memory SQLite)
    5. Import sensor CSV into session database (if provided)
    6. Validate filename template against known keys (if template supplied)
    7. Plan frame offsets → write frame_plan to session database
    8. Extract frames and write to disk, applying metadata to each file

Output mode is controlled by spec.stream_output (set in YAML):
    False (default): frames are buffered per VideoExtractionPlan and written
        as a batch after each video completes.  Peak memory scales with
        frames-per-video (~24 MB per 4K frame).
    True: each frame is written to disk immediately after decoding.  Peak
        memory is a single frame (~24 MB at 4K) regardless of session length.
        Use this for dense extraction intervals or long sessions.
"""

from pathlib import Path

from ..config.spec_parser import spec_from_file
from ..config.video_discovery import discover_videos
from ..data.importer import import_csv
from ..db.session_db import create_session_db, close_session_db
from ..extraction.frame_extractor import extract_frames
from ..extraction.video_reader import probe_video
from ..extraction.video_session import create_video_session
from ..models.models import ExtractionSpec
from ..metadata.ifdo import write_ifdo_manifest
from ..output.output_frames import output_frames, write_frame
from ..planning.planner import plan


def run(
    spec_path: Path,
    video_source: Path | list[Path],
    output_dir: Path,
    csv_path: Path | None = None,
) -> None:
    """Execute a full extraction run from spec to annotated image files on disk.

    Stage order:
        1. Parse spec from YAML
        2. Discover and probe video files → VideoSession
        3. Initialise in-memory session database
        4. Import sensor CSV (if provided)
        5. Validate filename template (if supplied)
        6. Plan frame offsets → write frame_plan to session DB
        7. Extract and write frames (mode depends on spec.stream_output):
               False (default): buffer per VideoExtractionPlan, write batch
                   via output_frames after each video completes
               True: write each frame immediately via write_frame as yielded
           In both modes, EXIF/IPTC/XMP are embedded in a single Pillow save
           per frame — no post-hoc metadata re-write.
        8. Write iFDO JSON sidecar manifest for the full image set
        9. Close session database

    Args:
        spec_path:    path to the YAML extraction spec.
        video_source: directory of video files, or an explicit list of paths.
        output_dir:   directory to write output image files into.
        csv_path:     path to sensor CSV, or None if no sensor data.

    Raises:
        FileNotFoundError: if spec_path, any video file, or csv_path does not
                           exist.
        ValueError:        if the spec is invalid, the filename template
                           references an unknown key, or any planned timestamp
                           falls outside the video session span.
        OSError:           if output_dir cannot be created or a file cannot be
                           written.
    """
    pass
