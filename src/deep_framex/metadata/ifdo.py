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

import json
import uuid
from pathlib import Path

from ..models.core import FrameMetadata
from ..utils.coordinates import normalize_longitude


def write_ifdo_manifest(
    written: list[tuple[Path, FrameMetadata]],
    output_dir: Path,
) -> Path:
    """Write an iFDO JSON sidecar manifest for a completed extraction run.

    Builds one entry per frame keyed by filename, assembles the image-set-header
    from project_metadata shared across all frames, and writes the manifest as
    a JSON file into output_dir.

    Entries are sorted by utc_timestamp before writing so the manifest is in
    chronological order regardless of the order workers finished.

    Args:
        written:    list of (path, FrameMetadata) pairs — as returned by
                    output_frames, or collected from streaming / parallel workers.
                    Pixel data is not needed here and should already be discarded.
        output_dir: directory where the manifest will be written.  Must exist.

    Returns:
        Path to the written manifest file.

    Raises:
        OSError: if the manifest file cannot be written.
    """
    written = sorted(written, key=lambda pair: pair[1].utc_timestamp)

    # Build the image-set-header from the first frame's project_metadata.
    # All frames in a run share the same project_metadata, so any frame works.
    header: dict = {}
    if written:
        pm = written[0][1].project_metadata
        if "cruise_id" in pm:
            header["image-set-name"] = pm["cruise_id"]
        if "project" in pm:
            header["image-abstract"] = pm["project"]
        if "license" in pm:
            header["image-license"] = pm["license"]
        if "vehicle" in pm:
            header["image-platform"] = {"name": pm["vehicle"]}
        pi: dict = {}
        if "pi_name" in pm:
            pi["name"] = pm["pi_name"]
        if "pi_orcid" in pm:
            pi["orcid"] = pm["pi_orcid"]
        if pi:
            header["image-pi"] = pi

    # Build one entry per frame.
    items: dict = {}
    for path, meta in written:
        entry: dict = {
            "image-uuid": str(uuid.uuid4()),
            "image-datetime": meta.utc_timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        }

        snap = meta.sensor_snapshot
        if "latitude" in snap:
            entry["image-latitude"] = snap["latitude"]
        if "longitude" in snap:
            entry["image-longitude"] = normalize_longitude(snap["longitude"])
        if "depth" in snap:
            entry["image-depth"] = snap["depth"]
        if "altitude" in snap:
            entry["image-altitude-meters"] = snap["altitude"]
        if "heading" in snap:
            entry["image-heading"] = snap["heading"]
        if "pitch" in snap:
            entry["image-pitch"] = snap["pitch"]
        if "roll" in snap:
            entry["image-roll"] = snap["roll"]

        pm = meta.project_metadata
        if "cruise_id" in pm:
            entry["image-sequence-name"] = pm["cruise_id"]
        if "dive_id" in pm:
            entry["image-deployment-id"] = pm["dive_id"]
        if "vehicle" in pm:
            entry["image-platform"] = {"name": pm["vehicle"]}
        pi = {}
        if "pi_name" in pm:
            pi["name"] = pm["pi_name"]
        if "pi_orcid" in pm:
            pi["orcid"] = pm["pi_orcid"]
        if pi:
            entry["image-pi"] = pi
        if "project" in pm:
            entry["image-abstract"] = pm["project"]
        if "license" in pm:
            entry["image-license"] = pm["license"]

        items[path.name] = entry

    manifest = {
        "image-set-header": header,
        "image-set-items": items,
    }

    manifest_path = output_dir / "ifdo.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path
