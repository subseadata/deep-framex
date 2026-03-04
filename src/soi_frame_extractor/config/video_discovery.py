"""Video discovery

Resolves a user-supplied source (directory or an explicit list of
paths) into a list of probed VideoFile objects ready to be assembled
into a VideoSession.
"""

from pathlib import Path

from ..models.models import VideoFile
from ..extraction.video_reader import probe_video

# TODO: evaluate whether other formats (.avi, .mkv, .mts, .m4v) are needed
VIDEO_EXTENSIONS = {".mp4", ".mov"}

def discover_videos(source: Path | list[Path]) -> list[VideoFile]:
    """Resolve a source to a list of probed VideoFiles.

    Accepts either a directory (all recognised video files within it are
    discovered) or an explicit list of file paths.  Does not recurse into
    subdirectories.  Probing order within a directory is filesystem order;
    callers should pass the result to create_video_session for sorting.

    Args:
        source: a Path to a directory, or a list of Paths to video files.

    Returns:
        List of probed VideoFile objects (unsorted).

    Raises:
        FileNotFoundError: if source (or any file in the list) does not exist.
        ValueError: if source is a directory but contains no recognised video
                    files, or if source is a file path rather than a directory
                    (use an explicit list for single-file ingress).
        ValueError: if any file in an explicit list has an unrecognised
                    extension.
    """
    # if source is a list:
    #   delegate to _probe_file_list(source)
    # else if source is a Path:
    #   if it does not exist: raise FileNotFoundError
    #   if it is a file: raise ValueError (wrap it in a list if single-file)
    #   if it is a directory: delegate to _probe_directory(source)
    pass


def _probe_directory(directory: Path) -> list[VideoFile]:
    """Discover and probe all recognised video files in a directory.

    Args:
        directory: path to an existing directory.

    Returns:
        List of probed VideoFile objects.

    Raises:
        ValueError: if no video files with recognised extensions are found.
    """
    # collect all files in directory whose suffix (lowercased) is in VIDEO_EXTENSIONS
    # raise ValueError if the collected list is empty
    # probe each path via probe_video and collect results
    # return the list of VideoFiles
    pass


def _probe_file_list(paths: list[Path]) -> list[VideoFile]:
    """Probe an explicit list of video file paths.

    Args:
        paths: list of paths to video files.

    Returns:
        List of probed VideoFile objects, in the same order as input.

    Raises:
        FileNotFoundError: if any path does not exist.
        ValueError: if any path has an unrecognised extension.
    """
    # for each path:
    #   raise FileNotFoundError if it does not exist
    #   raise ValueError if suffix (lowercased) is not in VIDEO_EXTENSIONS
    #   probe via probe_video
    # return list of VideoFiles
    pass
