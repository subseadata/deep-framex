"""Video read functions

Reads a video file into Video container or reads video metadata into VideoFile object.
"""

import av
from pathlib import Path

from ..models.models import Video, VideoFile


def open_video(video_file: VideoFile) -> Video:
    """Open a VideoFile into a PyAV container and return a Video.

    Args:
        video_file (VideoFile): video file metadata including path, utc_start and duration.

    Returns:
        Video containing the VideoFile and its open PyAV container.

    Raises:
        FileNotFoundError: if video_file.path does not exist.
    """
    pass

def probe_video(path: Path) -> VideoFile:
    """Probe a video file and return a fully populated VideoFile.

    Reads container metadata via ffprobe without opening a decode context.

    Args:
        path (Path): path to the video file.

    Returns:
        VideoFile with path, utc_start, and duration populated.

    Raises:
        FileNotFoundError: if path does not exist.
        ValueError: if utc_start or duration cannot be read from the file metadata.
    """
    pass
