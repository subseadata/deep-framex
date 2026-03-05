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

import json
import sqlite3
from collections.abc import Iterator
from datetime import timedelta

import av
import numpy as np

from ..models.models import ExtractedFrame, FrameMetadata, VideoExtractionPlan
from .video_reader import open_video


def extract_frames(
    planned: list[VideoExtractionPlan],
    conn: sqlite3.Connection,
    project_metadata: dict[str, str] = {},
) -> Iterator[ExtractedFrame]:
    """Yield fully annotated ExtractedFrames at planned offsets across all videos.

    Opens each video in turn, seeks to each planned offset, decodes the
    closest frame, reads its sensor_snapshot from frame_plan, and yields
    an ExtractedFrame.  The video container is closed before moving to the
    next video.  Frames are yielded one at a time — the caller controls
    whether to accumulate them or write them to disk immediately.

    Args:
        planned:          list of VideoExtractionPlan objects, each containing a
                          VideoFile and sorted list of offsets in seconds from t=0.
        conn:             active session database connection; used to read
                          sensor_snapshot from frame_plan for each frame.
        project_metadata: project-level metadata from the ExtractionSpec,
                          written into every frame's FrameMetadata unchanged.

    Yields:
        ExtractedFrame for each planned offset, in video order then ascending
        offset within each video.

    Raises:
        FileNotFoundError: if any video file path does not exist at extraction
                           time.
        RuntimeError: if a planned frame cannot be decoded at its offset.
    """
    for plan in planned:
        video = open_video(plan.video_file)
        try:
            stream = video.container.streams.video[0]
            for offset_s in plan.offsets_s:
                pts = int(offset_s / stream.time_base)

                # Seek to the nearest keyframe at or before the target PTS, then
                # decode forward to find the frame whose PTS is closest to the target.
                # We compare the last frame before and the first frame after the target
                # and pick whichever is nearer.
                video.container.seek(pts, stream=stream)
                prev_frame = None
                closest_frame = None
                for packet in video.container.demux(stream):
                    for f in packet.decode():
                        if f.pts is None:
                            continue
                        if f.pts <= pts:
                            prev_frame = f
                        else:
                            if prev_frame is None:
                                closest_frame = f
                            elif abs(f.pts - pts) < abs(prev_frame.pts - pts):
                                closest_frame = f
                            else:
                                closest_frame = prev_frame
                            break
                    if closest_frame is not None:
                        break
                if closest_frame is None:
                    closest_frame = prev_frame
                if closest_frame is None:
                    raise RuntimeError(
                        f"Could not decode frame at offset {offset_s}s "
                        f"in {plan.video_file.path}"
                    )

                ndarray = closest_frame.to_ndarray(format="rgb24")
                utc_timestamp = plan.video_file.utc_start + timedelta(seconds=offset_s)

                row = conn.execute(
                    "SELECT sensor_snapshot FROM frame_plan "
                    "WHERE video_path = ? AND offset_s = ?",
                    (str(plan.video_file.path), offset_s),
                ).fetchone()
                sensor_snapshot = json.loads(row[0]) if row and row[0] else {}

                yield ExtractedFrame(
                    frame=ndarray,
                    metadata=FrameMetadata(
                        utc_timestamp=utc_timestamp,
                        video_path=plan.video_file.path,
                        offset_s=offset_s,
                        sensor_snapshot=sensor_snapshot,
                        project_metadata=project_metadata,
                    ),
                )
        finally:
            video.container.close()
