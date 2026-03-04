"""Frame extractor

Extracts frames from video files at pre-planned offsets and assembles
ExtractedFrame objects by pairing each raw frame with its FrameMetadata
from the session database frame_plan table.

For each VideoExtractionPlan, the extractor opens the video container once,
seeks to each offset in ascending order (minimising seek distance), decodes
the frame, reads the corresponding sensor_snapshot from frame_plan, builds
a FrameMetadata, and yields an ExtractedFrame.  The container is closed
before moving to the next video.
"""

import sqlite3

from ..models.models import ExtractedFrame, FrameMetadata, VideoExtractionPlan


def extract_frames(
    planned: list[VideoExtractionPlan],
    conn: sqlite3.Connection,
) -> list[ExtractedFrame]:
    """Extract frames at planned offsets and return fully annotated ExtractedFrames.

    Reads sensor_snapshot and project_metadata for each frame from the
    frame_plan table in the session database, combining them with the decoded
    pixel data into ExtractedFrame objects.

    Args:
        planned: list of VideoExtractionPlan objects, each containing a
                 VideoFile and sorted list of offsets in seconds from t=0.
        conn:    active session database connection; used to read
                 sensor_snapshot from frame_plan for each frame.

    Returns:
        List of ExtractedFrame in the order frames were planned across all
        videos (video order, then ascending offset within each video).

    Raises:
        FileNotFoundError: if any video file path does not exist at extraction
                           time.
        RuntimeError: if a planned frame cannot be decoded at its offset.
    """
    # for each plan in planned:
    #   open av container for plan.video_file.path
    #   for each offset_s in plan.offsets_s:
    #     seek container to offset_s
    #     decode next video frame → NDArray (H, W, 3) uint8 RGB
    #     compute utc_timestamp = plan.video_file.utc_start + timedelta(seconds=offset_s)
    #     query frame_plan for row where video_path == plan.video_file.path
    #       and offset_s == offset_s → read sensor_snapshot (JSON) and project_metadata
    #     build FrameMetadata(utc_timestamp, video_path, offset_s, sensor_snapshot, project_metadata)
    #     append ExtractedFrame(frame=ndarray, metadata=frame_metadata)
    #   close container
    # return results
    pass
