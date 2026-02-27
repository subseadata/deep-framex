"""Frame extractor function

Extracts frames from video files at pre-planned offsets.
"""

import numpy as np

from ..models.models import VideoExtractionPlan


def extract_frames(planned: list[VideoExtractionPlan]) -> list[np.ndarray]:
    """Extract frames from video files at pre-planned offsets.

    For each VideoExtractionPlan, opens the video container once, seeks to
    each offset in order, grabs the frame, then closes before moving to the
    next video.

    Args:
        planned: List of VideoExtractionPlan objects, each containing a
                 VideoFile and sorted list of offsets in seconds from t=0.

    Returns:
        List of (H, W, 3) uint8 RGB numpy arrays in the order they were
        planned across all videos.
    """
    # for each plan:
    #   open av container for plan.video_file.path
    #   for each offset in plan.offsets_s:
    #     seek to offset
    #     decode and grab first frame
    #     append to results
    #   close container
    pass
