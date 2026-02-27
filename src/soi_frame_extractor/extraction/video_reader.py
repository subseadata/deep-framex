"""Video reader

Opens a video file into a PyAV container for use by VideoSession.
"""

import av
from pathlib import Path


def open_video(path: Path) -> av.container.InputContainer:
    """Open a video file and return a PyAV container.

    Args:
        path (Path): path to the video file.

    Returns:
        Open PyAV InputContainer.

    Raises:
        FileNotFoundError: if path does not exist.
    """
    pass
