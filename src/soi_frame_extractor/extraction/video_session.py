"""Video session

Handles video session logic. Video sessions are collections of (typically consecutive) videos probed by video_reader.
"""

from ..models.models import VideoFile, VideoSession


def create_video_session(video_files: list[VideoFile]) -> VideoSession:
    """Create a VideoSession by sorting VideoFiles by utc_start.

    Args:
        video_files: List of probed VideoFile objects

    Returns:
        VideoSession with videos sorted by utc_start
    """
    # sort video_files by utc_start and return as a VideoSession
    pass
