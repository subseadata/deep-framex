"""Frame extractor

Extracts frames from a single VideoExtractionPlan and yields ExtractedFrame
objects ready for writing.

The plan is self-contained: it carries the video file path, the list of offsets
to extract, the interpolated sensor values at each offset, and the project
metadata.  No database connection is needed — everything the extractor requires
travels with the plan.

This makes decode_frames suitable for use in a worker process or on a remote
machine: receive a plan (e.g. deserialised from JSON), open the video file, and
yield frames.  The only external dependency is that plan.video_file.path must
be readable on the machine running this function.

NOTE for cloud / distributed use: if video files are stored on S3, GCS, or
another remote store, they must either be downloaded to local disk first or
accessed via a URL.  PyAV can open HTTP/HTTPS URLs directly
(av.open("https://...")) and may support s3:// if ffmpeg is built with the
relevant protocol.  To enable this, video_file.path would need to accept a
URL string rather than a Path — that change lives in open_video (video_reader.py)
and VideoFile (models.py).
"""

from collections.abc import Iterator
from datetime import timedelta

from ..models.models import ExtractedFrame, FrameMetadata, VideoExtractionPlan
from .video_reader import open_video


def decode_frames(
    plan: VideoExtractionPlan,
) -> Iterator[ExtractedFrame]:
    """Yield fully annotated ExtractedFrames for all planned offsets in one video.

    Opens the video file once, seeks to each planned offset in ascending order
    (minimising seek distance), decodes the closest frame, and yields an
    ExtractedFrame with sensor values and project metadata embedded.  The video
    container is closed when all frames have been yielded or if an error occurs.

    All inputs come from the plan — no database connection is needed.  The plan
    is a self-contained unit of work that can be serialised to JSON and executed
    on any machine that can read plan.video_file.path.

    Args:
        plan: a VideoExtractionPlan produced by plan().  Contains the video file
              path, sorted frame offsets, sensor snapshots, and project metadata.

    Yields:
        ExtractedFrame for each planned offset in ascending offset order.

    Raises:
        FileNotFoundError: if plan.video_file.path does not exist.
        RuntimeError: if a planned frame cannot be decoded at its offset.
    """
    video = open_video(plan.video_file)
    try:
        stream = video.container.streams.video[0]
        for frame_spec in plan.frames:
            offset_s = frame_spec.offset_s
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

            yield ExtractedFrame(
                frame=ndarray,
                metadata=FrameMetadata(
                    utc_timestamp=utc_timestamp,
                    video_path=plan.video_file.path,
                    offset_s=offset_s,
                    sensor_snapshot=frame_spec.sensor_snapshot,
                    project_metadata=plan.project_metadata,
                ),
            )
    finally:
        video.container.close()
