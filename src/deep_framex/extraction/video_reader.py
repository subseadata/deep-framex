"""Video read functions

Reads a video file into a Video container, or probes it for metadata only.

utc_start precedence: an explicit utc_start argument wins; otherwise the
container's format.tags.creation_time, then the video stream's own
creation_time tag, which QuickTime/MOV and MP4 files embed as an ISO 8601 UTC
string.  If none of the three is available, probe_video raises ValueError.

duration is read from the container's format duration field (seconds as float).
"""

import av
from datetime import datetime, timedelta
from pathlib import Path

from ..models.core import Video, VideoFile


def open_video(video_file: VideoFile) -> Video:
    """Open a VideoFile into a PyAV container and return a Video.

    Args:
        video_file: VideoFile metadata including path, utc_start, and duration.

    Returns:
        Video containing the VideoFile and its open PyAV container.

    Raises:
        FileNotFoundError: if video_file.path does not exist.
    """
    if not video_file.path.exists():
        raise FileNotFoundError(f"Video file not found: {video_file.path}")
    container = av.open(str(video_file.path))
    return Video(file=video_file, container=container)


def probe_video(path: Path, utc_start: datetime | None = None) -> VideoFile:
    """Probe a video file and return a fully populated VideoFile.

    Reads container metadata via PyAV without opening a full decode context.
    Without an utc_start override, utc_start is sourced from
    container.metadata['creation_time'], with a fallback to the first video
    stream's creation_time tag.  duration comes from container.duration
    (microseconds).

    Args:
        path: path to the video file.
        utc_start: UTC start time override.  When given, the creation_time tag
                   is not read at all (used for unclocked video, see the spec's
                   video_start_times block).

    Returns:
        VideoFile with path, utc_start, and duration populated.

    Raises:
        FileNotFoundError: if path does not exist.
        ValueError: if duration cannot be determined, or — with no utc_start
                    override — if creation_time is absent from both container
                    and video stream tags, or its datetime is not UTC-aware.
    """
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {path}")

    with av.open(str(path), metadata_errors="ignore") as container:
        if utc_start is None:
            creation_time_str = container.metadata.get("creation_time")

            if creation_time_str is None:
                for stream in container.streams.video:
                    creation_time_str = stream.metadata.get("creation_time")
                    if creation_time_str:
                        break

            if creation_time_str is None:
                raise ValueError(
                    f"No creation_time tag found in {path}. "
                    "Re-encode with '-metadata creation_time=...' or set video_start_times in the spec."
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
