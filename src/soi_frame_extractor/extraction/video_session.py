"""Video session

Assembles a sorted VideoSession from a list of probed VideoFile objects.

Videos are ordered by utc_start.  Gaps between videos are permitted — the
planner's _assign_to_video will raise ValueError for any planned timestamp
that falls in a gap, so gap handling is the caller's responsibility.
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
