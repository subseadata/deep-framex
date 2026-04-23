"""deep-framex public API.

Import what you need directly from the package:

    from deep_framex import extract
    from deep_framex import spec_from_file, plan, FrameMetadata
"""

# Main entry point
from deep_framex.pipeline import extract

# Spec and video setup
from deep_framex.config.spec_parser import spec_from_file, spec_from_dict
from deep_framex.config.video_discovery import discover_videos
from deep_framex.extraction.video_session import create_video_session

# Planning
from deep_framex.planning.planner import plan, interpolate_sensor
from deep_framex.db.session_db import create_session_db, close_session_db
from deep_framex.data.importer import import_csv

# Extraction and writing
from deep_framex.extraction.frame_extractor import decode_frames
from deep_framex.output.output_frames import write_frame
from deep_framex.metadata.ifdo import write_ifdo_manifest
from deep_framex.metadata.biigle import write_biigle_manifest

# BIIGLE assembly from existing frames
from deep_framex.metadata.assemble import assemble_biigle_records
from deep_framex.utils.timestamps import parse_filename_template, parse_file_list_csv

# Models
from deep_framex.models.core import (
    ExtractionSpec,
    ExtractionRule,
    ColumnMappings,
    VideoExtractionPlan,
    FrameMetadata,
    ExtractedFrame,
    TimePeriod,
)

__all__ = [
    # Entry point
    "extract",
    # Spec and setup
    "spec_from_file",
    "spec_from_dict",
    "discover_videos",
    "create_video_session",
    # Planning
    "plan",
    "interpolate_sensor",
    "create_session_db",
    "close_session_db",
    "import_csv",
    # Extraction and writing
    "decode_frames",
    "write_frame",
    "write_ifdo_manifest",
    "write_biigle_manifest",
    # BIIGLE assembly
    "assemble_biigle_records",
    "parse_filename_template",
    "parse_file_list_csv",
    # Models
    "ExtractionSpec",
    "ExtractionRule",
    "ColumnMappings",
    "VideoExtractionPlan",
    "FrameMetadata",
    "ExtractedFrame",
    "TimePeriod",
]
