"""Metadata builders for EXIF, IPTC, and XMP layers.

Assembles per-image metadata for extracted frames.  Each build function
returns metadata in the format expected by Pillow at save time, so all
layers are embedded in a single file write — no post-hoc re-opening.

    _build_exif(meta) → bytes   piexif-encoded EXIF block
    _build_iptc(meta) → bytes   raw IPTC IIM block
    _build_xmp(meta, ns_uri, ns_prefix) → bytes   serialised XMP packet

iFDO is NOT handled here.  iFDO is a standalone JSON sidecar file written
once per extraction run by metadata/ifdo.py — it is not embedded in image files.

Routing is governed by FIELD_REGISTRY for known canonical fields (utc_timestamp,
latitude, longitude, depth, etc.).  Any sensor column or project_metadata key
not present in FIELD_REGISTRY is written to XMP under a user-configurable
custom namespace.  The namespace URI and prefix are taken from ExtractionSpec
(xmp_namespace_uri, xmp_namespace_prefix) and default to
"https://soi-frame-extractor.org/xmp/v1/" / "sfe".

Coordinate conventions:
    Input:   decimal degrees; longitude accepts both −180/+180 and 0–360.
    EXIF:    absolute DMS rational triples + Ref tags (N/S, E/W) — no negatives.
    XMP:     signed decimal degrees (−180/+180), negative = S or W.

    Longitude normalisation (0–360 → −180/+180) is applied internally before
    any layer-specific conversion.

GPS altitude: depth sensor value written to GPSAltitude with GPSAltitudeRef=1
(below sea level).  Depth is treated as a positive magnitude; no sign flip needed.

UTC timestamp is written to DateTimeOriginal, GPSDateStamp, and GPSTimeStamp.

This module does not validate that the image format supports all layers;
callers should use JPEG or TIFF which support the full set.
"""

from pathlib import Path

from ..models.models import FIELD_REGISTRY, FrameMetadata
from ..utils.coordinates import decimal_to_dms, decimal_to_ref, normalize_longitude

_DEFAULT_XMP_NS_URI = "https://soi-frame-extractor.org/xmp/v1/"
_DEFAULT_XMP_NS_PREFIX = "sfe"


def _build_exif(meta: FrameMetadata) -> bytes:
    """Build a piexif-encoded EXIF block from FrameMetadata.

    Longitude is normalised to −180/+180 before conversion.  All GPS values
    are passed as absolute magnitudes; hemisphere is encoded in Ref tags.

    Tags built (where values are present in meta):
        DateTimeOriginal        — from utc_timestamp
        GPSDateStamp            — date portion of utc_timestamp
        GPSTimeStamp            — time portion of utc_timestamp
        GPSLatitude             — abs(latitude) as DMS rational via decimal_to_dms
        GPSLatitudeRef          — "N" or "S" via decimal_to_ref
        GPSLongitude            — abs(longitude) as DMS rational via decimal_to_dms
        GPSLongitudeRef         — "E" or "W" via decimal_to_ref
        GPSAltitude             — depth value as rational (positive magnitude)
        GPSAltitudeRef          — 1 (below sea level)
        Make                    — from project_metadata camera_make
        Model                   — from project_metadata camera_model

    Args:
        meta: FrameMetadata supplying utc_timestamp, sensor_snapshot,
              and project_metadata.

    Returns:
        piexif-encoded bytes ready to pass to Pillow's exif parameter at save time.
    """
    pass


def _build_iptc(meta: FrameMetadata) -> bytes:
    """Build a raw IPTC IIM block from FrameMetadata.

    GPS coordinates are NOT written to IPTC — IIM Record 2 has no GPS fields.

    Fields built (where values are present in project_metadata):
        Credit                  — credit
        Source                  — source
        CopyrightNotice         — copyright
        Caption-Abstract        — caption
        DateCreated             — date portion of utc_timestamp
        TimeCreated             — time portion of utc_timestamp

    Args:
        meta: FrameMetadata supplying utc_timestamp and project_metadata.

    Returns:
        Raw IPTC IIM bytes ready to embed at Pillow save time.
    """
    pass


def _build_xmp(
    meta: FrameMetadata,
    xmp_namespace_uri: str,
    xmp_namespace_prefix: str,
) -> bytes:
    """Build a serialised XMP packet from FrameMetadata.

    Standard XMP properties built:
        xmp:CreateDate          — from utc_timestamp (ISO 8601)
        xmp:MetadataDate        — current wall-clock time (ISO 8601)

    Custom namespace properties (URI and prefix supplied by caller):
        All keys in sensor_snapshot not routed elsewhere by FIELD_REGISTRY.
        All keys in project_metadata not routed elsewhere by FIELD_REGISTRY.

    Args:
        meta:                 FrameMetadata supplying utc_timestamp,
                              sensor_snapshot, and project_metadata.
        xmp_namespace_uri:    URI registered for the custom namespace.
        xmp_namespace_prefix: prefix used when writing custom namespace properties.

    Returns:
        Serialised XMP packet bytes ready to embed at Pillow save time.
    """
    pass


def _unrouted_sensor_keys(meta: FrameMetadata) -> list[str]:
    """Return sensor_snapshot keys that are not claimed by FIELD_REGISTRY.

    Used by _write_xmp to determine which sensor columns fall through to
    the custom XMP namespace.

    Args:
        meta: FrameMetadata whose sensor_snapshot keys are inspected.

    Returns:
        List of key strings present in sensor_snapshot but absent from
        FIELD_REGISTRY.
    """
    pass


def _unrouted_project_keys(meta: FrameMetadata) -> list[str]:
    """Return project_metadata keys that are not claimed by FIELD_REGISTRY.

    Used by _write_xmp to determine which project_metadata fields fall
    through to the custom XMP namespace.

    Args:
        meta: FrameMetadata whose project_metadata keys are inspected.

    Returns:
        List of key strings present in project_metadata but absent from
        FIELD_REGISTRY.
    """
    pass
