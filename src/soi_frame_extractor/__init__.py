"""soi-frame-extractor public API.

Import what you need directly from the package:

    from soi_frame_extractor import extract
    from soi_frame_extractor import spec_from_file, plan, FrameMetadata
"""

# Main entry point
from soi_frame_extractor.pipeline import extract

# Spec and video setup
from soi_frame_extractor.config.spec_parser import spec_from_file, spec_from_dict
from soi_frame_extractor.config.video_discovery import discover_videos
from soi_frame_extractor.extraction.video_session import create_video_session

# Planning
from soi_frame_extractor.planning.planner import plan, interpolate_sensor
from soi_frame_extractor.db.session_db import create_session_db, close_session_db
from soi_frame_extractor.data.importer import import_csv

# Extraction and writing
from soi_frame_extractor.extraction.frame_extractor import decode_frames
from soi_frame_extractor.output.output_frames import write_frame
from soi_frame_extractor.metadata.ifdo import write_ifdo_manifest
from soi_frame_extractor.metadata.biigle import write_biigle_manifest

# BIIGLE assembly from existing frames
from soi_frame_extractor.metadata.assemble import assemble_biigle_records
from soi_frame_extractor.utils.timestamps import parse_filename_template, parse_file_list_csv

# Models
from soi_frame_extractor.models.core import (
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
