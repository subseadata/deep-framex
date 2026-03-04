"""Frame writer

Saves extracted frames to disk as image files.

Filenames are derived from each frame's UTC timestamp, making them
self-describing and chronologically sortable:

    <utc_timestamp>_<video_stem>.jpg
    e.g. 20251115T102530000000_dive_042.jpg

UTC timestamp is formatted as %Y%m%dT%H%M%S%f (microsecond precision) to
avoid collisions between frames from different videos at the same second.
If a collision still occurs (two frames with the same timestamp from the
same video stem), a zero-padded counter suffix is appended.

Output format is JPEG by default.  TIFF is also supported for lossless
archival.  Format is specified per call; all frames in one call are written
in the same format.

The output directory is created if it does not exist.
"""

from pathlib import Path

from ..models.models import ExtractedFrame


def output_frames(
    frames: list[ExtractedFrame],
    output_dir: Path,
    format: str = "jpeg",
) -> list[tuple[Path, ExtractedFrame]]:
    """Write extracted frames to disk and return paths paired with their frames.

    Creates output_dir if it does not exist.  Generates a filename for each
    frame via _frame_filename, resolves any collisions, writes the image, and
    returns a list of (path, frame) pairs suitable for passing directly to
    apply_metadata.

    Args:
        frames:     list of ExtractedFrame objects to write.
        output_dir: directory to write image files into.
        format:     image format — "jpeg" (default) or "tiff".

    Returns:
        List of (Path, ExtractedFrame) pairs, one per written frame, in the
        same order as the input list.

    Raises:
        ValueError: if format is not "jpeg" or "tiff".
        OSError: if output_dir cannot be created or a file cannot be written.
    """
    # raise ValueError if format is not in {"jpeg", "tiff"}
    # create output_dir (and any parents) if it does not exist
    #
    # seen: set[str] to track used stems for collision detection
    #
    # results = []
    # for each frame in frames:
    #   stem = _frame_filename(frame)
    #   if stem already in seen:
    #     append incrementing counter suffix until unique
    #   mark stem as seen
    #   path = output_dir / f"{stem}.jpg" or .tif depending on format
    #   write frame.frame (NDArray, RGB uint8) to path
    #   append (path, frame) to results
    #
    # return results
    pass


def _frame_filename(frame: ExtractedFrame) -> str:
    """Generate a filename stem for a frame from its metadata.

    Format: <utc_timestamp>_<video_stem>
    Example: 20251115T102530123456_dive_042

    The video stem is the source video filename without extension.
    No file extension is included — the caller appends the appropriate suffix.

    Args:
        frame: ExtractedFrame whose metadata supplies utc_timestamp and
               video_path.

    Returns:
        Filename stem as a string.
    """
    # format frame.metadata.utc_timestamp as %Y%m%dT%H%M%S%f
    # take frame.metadata.video_path.stem as the video stem
    # return f"{timestamp_str}_{video_stem}"
    pass
