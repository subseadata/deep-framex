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
    if isinstance(source, list):
        return _probe_file_list(source)
    if not source.exists():
        raise FileNotFoundError(f"Video source not found: {source}")
    if source.is_file():
        raise ValueError(
            f"{source} is a file, not a directory. "
            "To use a single video file, wrap it in a list: [path]"
        )
    return _probe_directory(source)


def _probe_directory(directory: Path) -> list[VideoFile]:
    """Discover and probe all recognised video files in a directory.

    Args:
        directory: path to an existing directory.

    Returns:
        List of probed VideoFile objects.

    Raises:
        ValueError: if no video files with recognised extensions are found.
    """
    paths = [p for p in directory.iterdir() if p.suffix.lower() in VIDEO_EXTENSIONS]
    if not paths:
        raise ValueError(
            f"No recognised video files found in {directory}. "
            f"Supported extensions: {sorted(VIDEO_EXTENSIONS)}"
        )
    return [probe_video(p) for p in paths]


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
    result = []
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {path}")
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            raise ValueError(
                f"Unrecognised video extension {path.suffix!r} for {path}. "
                f"Supported extensions: {sorted(VIDEO_EXTENSIONS)}"
            )
        result.append(probe_video(path))
    return result
