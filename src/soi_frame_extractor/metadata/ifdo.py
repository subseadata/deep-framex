"""iFDO manifest writer

Writes a single iFDO-compliant JSON sidecar file for a completed extraction
run.  iFDO (Image FAIR Data Object) is a per-image-set metadata standard —
one JSON file covers all images in the set, with one entry per image keyed
by filename.

Structure:
    {
        "image-set-header": {
            "image-set-name":   cruise_id from project_metadata,
            ...
        },
        "image-set-items": {
            "frame_20251015T101500.jpg": {
                "image-uuid":      UUID4 generated at write time,
                "image-datetime":  ISO 8601 UTC,
                "image-latitude":  signed decimal degrees,
                "image-longitude": signed decimal degrees (normalised −180/+180),
                "image-depth":     float,
                ...
            },
            ...
        }
    }

Coordinate conventions:
    Longitude normalised to −180/+180 before writing.
    Signed decimal degrees throughout — negative = S or W.

iFDO fields written per image (where values are present in FrameMetadata):
    image-uuid              — UUID4 generated at write time
    image-datetime          — utc_timestamp as ISO 8601
    image-latitude          — from sensor_snapshot latitude
    image-longitude         — from sensor_snapshot longitude (normalised)
    image-depth             — from sensor_snapshot depth
    image-altitude-meters   — from sensor_snapshot altitude
    image-heading           — from sensor_snapshot heading
    image-pitch             — from sensor_snapshot pitch
    image-roll              — from sensor_snapshot roll
    image-sequence-name     — from project_metadata cruise_id
    image-deployment-id     — from project_metadata dive_id
    image-platform          — nested: {"name": vehicle}
    image-pi                — nested: {"name": pi_name, "orcid": pi_orcid}
    image-abstract          — from project_metadata project
    image-license           — from project_metadata license
"""

from pathlib import Path

from ..models.models import ExtractedFrame
from ..utils.coordinates import normalize_longitude


def write_ifdo_manifest(
    written: list[tuple[Path, ExtractedFrame]],
    output_dir: Path,
) -> Path:
    """Write an iFDO JSON sidecar manifest for a completed extraction run.

    Builds one entry per frame keyed by filename, assembles the image-set-header
    from project_metadata shared across all frames, and writes the manifest as
    a JSON file into output_dir.

    Args:
        written:    list of (path, ExtractedFrame) pairs as returned by
                    output_frames or accumulated during streaming extraction.
                    Order is preserved in the manifest.
        output_dir: directory where the manifest will be written.  Must exist.

    Returns:
        Path to the written manifest file.

    Raises:
        OSError: if the manifest file cannot be written.
    """
    pass
