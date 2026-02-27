"""Frame extractor function

Extracts a set of frames from a video file, based on input timestamps
"""

from datetime import datetime
import numpy as np

from ..models.models import VideoSession


def extract_frames(
        session: VideoSession,
        times: list[datetime]) -> list[np.ndarray]:
    """Extract frames from a video session at specific times.

    Returns one (H, W, 3) uint8 RGB frame per entry in times, in the same
    order. Callers are responsible for associating frames back to timestamps.

    Args:
        session (VideoSession): video session to sample
        times (list[datetime]): list of UTC datetimes for frame extraction

    Returns:
        List of (H, W, 3) uint8 RGB numpy arrays, one per requested time.

    Raises:
        TypeError: if times is not a list of datetime values
    """
    pass
