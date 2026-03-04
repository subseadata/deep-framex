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
    utc_start is sourced from format.tags.creation_time, with a fallback to
    the video stream's creation_time tag.  duration comes from the container
    format duration.

    Args:
        path: path to the video file.

    Returns:
        VideoFile with path, utc_start, and duration populated.

    Raises:
        FileNotFoundError: if path does not exist.
        ValueError: if creation_time is absent from both format and video
                    stream tags, or if the duration cannot be determined.
        ValueError: if the creation_time string is not a valid ISO 8601 UTC
                    datetime.
    """
    # TODO: add fallback for files without creation_time in container metadata —
    #       options include parsing UTC from filename patterns or accepting a
    #       user-supplied file→start-time mapping (e.g. two-column CSV).

    # open container with av.open(path, metadata_errors='ignore')
    # read utc_start:
    #   try format.metadata.get('creation_time')
    #   else try first video stream metadata.get('creation_time')
    #   raise ValueError if neither is present
    #   parse with datetime.fromisoformat; raise ValueError if naive
    # read duration from container.duration (microseconds as int) → timedelta
    #   raise ValueError if duration is None or <= 0
    # return VideoFile(path=path, utc_start=utc_start, duration=duration)
    pass
