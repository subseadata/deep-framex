"""Video read functions

Reads a video file into a Video container, or probes it for metadata only.

utc_start is read from the container's creation_time tag, which QuickTime/MOV
and MP4 files embed as an ISO 8601 UTC string.  The probe reads
format.tags.creation_time first, then falls back to the video stream's own
creation_time tag.  If neither is present, probe_video raises ValueError —
the caller must ensure files carry this tag.

duration is read from the container's format duration field (seconds as float).
"""

import av
from datetime import datetime, timedelta
from pathlib import Path

from ..models.models import Video, VideoFile


def open_video(video_file: VideoFile) -> Video:
    """Open a VideoFile into a PyAV container and return a Video.

    Args:
        video_file: VideoFile metadata including path, utc_start, and duration.

    Returns:
        Video containing the VideoFile and its open PyAV container.

    Raises:
        FileNotFoundError: if video_file.path does not exist.
    """
    pass


def probe_video(path: Path) -> VideoFile:
    """Probe a video file and return a fully populated VideoFile.

    Reads container metadata via PyAV without opening a full decode context.
    utc_start is sourced from container.metadata['creation_time'], with a
    fallback to the first video stream's creation_time tag.  duration comes
    from container.duration (microseconds).

    Args:
        path: path to the video file.

    Returns:
        VideoFile with path, utc_start, and duration populated.

    Raises:
        FileNotFoundError: if path does not exist.
        ValueError: if creation_time is absent from both container and video
                    stream tags, or if the datetime is not UTC-aware.
        ValueError: if duration cannot be determined.
    """
    # TODO: add fallback for files without creation_time in container metadata —
    #       options include parsing UTC from filename patterns or accepting a
    #       user-supplied file→start-time mapping (e.g. two-column CSV).

    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {path}")

    with av.open(str(path), metadata_errors="ignore") as container:
        creation_time_str = container.metadata.get("creation_time")

        if creation_time_str is None:
            for stream in container.streams.video:
                creation_time_str = stream.metadata.get("creation_time")
                if creation_time_str:
                    break

        if creation_time_str is None:
            raise ValueError(
                f"No creation_time tag found in {path}. "
                "Re-encode with '-metadata creation_time=...' or supply a start-time mapping."
            )

        utc_start = datetime.fromisoformat(creation_time_str)
        if utc_start.tzinfo is None:
            raise ValueError(
                f"creation_time in {path} is not UTC-aware: {creation_time_str!r}"
            )

        duration_us = container.duration
        if not duration_us:
            raise ValueError(f"Could not determine duration for {path}")
        duration = timedelta(microseconds=duration_us)

    return VideoFile(path=path, utc_start=utc_start, duration=duration)
