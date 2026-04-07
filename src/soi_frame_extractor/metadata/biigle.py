"""BIIGLE manifest writer

Writes a single BIIGLE CSV file for completed extraction run. BIIGLE is a
web service for the efficient and rapid annotation of still images and videos.

BIIGLE attempts to automatically read the metadata from the EXIF information
of JPEG files. This doesn't work for videos or if the images have another
format than JPEG. Instead, users can upload a simple CSV file. This function
creates and writes the BIIGLE compatible CSV file using available metadata
from video or supplied by the user in the input CSV sensor files.

Output CSV:
    Uses , as delimiter, " as enclosure, and \\ as escape character.

    Columns:
        filename                - mandatory, name of the file the metadata
                                 belongs to
        taken_at                - date time where file was taken
        lng                     - longitude, EPSG:4326 reference, decimal
                                 degrees, requires lat column is present
        lat                     - latitude, EPSG:4326 reference, decimal
                                 degrees, requires lng column is present
        gps_altitude            - meters, negative for depth
        distance_to_ground      - meters, distance to seafloor
        yaw                     - degrees, yaw/heading of the vehicle,
                                 0 is North, 90 is East

Note that BIIGLE accepts "area" as a CSV column input, but because this tool
is ROV-focused, we exclude this functionality for the time being. Fixed cameras
with area-based metadata could be added.
"""

import csv
from pathlib import Path

from ..models.models import FrameMetadata


def _build_biigle_row(path: Path, meta: FrameMetadata) -> dict:
    """Build a BIIGLE CSV row dictionary from FrameMetadata.

    Args:
        path:   Path to the written frame file.
        meta:   FrameMetadata with sensor_snapshot and project_metadata.

    Returns:
        Dict suitable for DictWriter with BIIGLE-compatible keys.
    """
    row = {
        "filename": path.name,
        "taken_at": meta.utc_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
    }

    snap = meta.sensor_snapshot

    # lat/lng as a pair (optional, but must appear together if present)
    if "latitude" in snap and "longitude" in snap:
        row["lat"] = str(snap["latitude"])
        row["lng"] = str(snap["longitude"])

    # gps_altitude: depth (positive) -> negative (below sea level)
    if "depth" in snap:
        row["gps_altitude"] = str(-snap["depth"])

    # distance_to_ground: altitude only
    if "altitude" in snap:
        row["distance_to_ground"] = str(snap["altitude"])

    # yaw/heading
    if "heading" in snap:
        row["yaw"] = str(snap["heading"])

    return row


def write_biigle_manifest(
    written: list[tuple[Path, FrameMetadata]],
    output_dir: Path,
) -> Path:
    """Write a BIIGLE-formatted CSV file for a completed extraction run.

    Builds one entry per frame keyed by filename, assembles CSV entries from
    project_metadata shared across all frame, and writes to CSV.

    Entries are sorted by utc timestamp.

    Args:
        written:    list of (path, FrameMetadata) pairs - as returned by
                    output_frames, or collected from workers.
        output_dir: directory where manifest will be written, must exist.

    Returns:
        Path to the written CSV file

    Raises:
        OSError:    if the file cannot be written.
    """
    written = sorted(written, key=lambda pair: pair[1].utc_timestamp)

    # Build all rows first to determine which columns are actually used
    rows = [_build_biigle_row(path, meta) for path, meta in written]

    # Build fieldnames in a fixed, predictable column order — only include
    # columns that appear in at least one row.
    _COLUMN_ORDER = ["filename", "taken_at", "lat", "lng", "gps_altitude",
                     "distance_to_ground", "yaw"]
    present = {key for row in rows for key in row}
    fieldnames = [col for col in _COLUMN_ORDER if col in present]

    manifest_path = output_dir / "biigle_metadata.csv"

    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames,
                                delimiter=",", quotechar='"',
                                escapechar="\\", quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)

    return manifest_path
