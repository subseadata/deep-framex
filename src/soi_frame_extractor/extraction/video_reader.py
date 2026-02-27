"""Video reader

Takes a VideoFile and opens it into a PyAV container, returning a Video object
ready for use by VideoSession.
"""

import av

from ..models.models import Video, VideoFile


def open_video(video_file: VideoFile) -> Video:
    """Open a VideoFile into a PyAV container and return a Video.

    Populates VideoFile.duration from the container on open.

    Args:
        video_file (VideoFile): video file metadata including path and utc_start.

    Returns:
        Video containing the VideoFile and its open PyAV container.

    Raises:
        FileNotFoundError: if video_file.path does not exist.
    """
    pass
