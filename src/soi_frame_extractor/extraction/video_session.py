"""Video session

Handles video session logic. Video sessions are collections of (typically consecutive) videos opened by video_reader.
"""

from ..models.models import Video, VideoFile, VideoSession
from .video_reader import open_video


def create_video_session(video_files: list[VideoFile]) -> VideoSession:
    """Create a VideoSession by opening each VideoFile in sequence using video_reader.
    
    Args:
        video_files: List of VideoFile objects to open
        
    Returns:
        VideoSession containing all successfully opened Video objects
    """
    # loop over list of video files and open each into a Video container, then bundle together in a session
    pass
