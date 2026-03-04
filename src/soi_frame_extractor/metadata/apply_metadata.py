"""Metadata writer

Embeds FrameMetadata into an extracted image file using up to four metadata
layers: EXIF, IPTC, XMP, and iFDO.

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
    iFDO:    signed decimal degrees (−180/+180), negative = S or W.

    Longitude normalisation (0–360 → −180/+180) is applied internally before
    any layer-specific conversion.

GPS altitude: depth sensor value written to GPSAltitude with GPSAltitudeRef=1
(below sea level).  Depth is treated as a positive magnitude; no sign flip needed.

UTC timestamp is written to DateTimeOriginal, GPSDateStamp, and GPSTimeStamp.

iFDO nested objects (image-platform, image-pi) are assembled from individual
project_metadata keys before serialisation.

This module does not validate that the image format supports all four layers;
callers should use JPEG or TIFF which support the full set.
"""

from pathlib import Path

from ..models.models import FIELD_REGISTRY, ExtractedFrame, FrameMetadata
from ..utils.coordinates import decimal_to_dms, decimal_to_ref, normalize_longitude

_DEFAULT_XMP_NS_URI = "https://soi-frame-extractor.org/xmp/v1/"
_DEFAULT_XMP_NS_PREFIX = "sfe"


def apply_metadata(
    path: Path,
    frame: ExtractedFrame,
    xmp_namespace_uri: str = _DEFAULT_XMP_NS_URI,
    xmp_namespace_prefix: str = _DEFAULT_XMP_NS_PREFIX,
) -> None:
    """Embed FrameMetadata into the image file at path.

    Reads the existing image file, writes metadata into all applicable
    layers (EXIF, IPTC, XMP, iFDO), and saves the file in place.

    Known fields are routed via FIELD_REGISTRY.  Sensor columns and
    project_metadata keys absent from the registry go to XMP under the
    provided custom namespace.  iFDO is serialised as a JSON block
    embedded in XMP.

    Args:
        path:                 absolute path to the image file to annotate.
        frame:                ExtractedFrame whose .metadata carries all values
                              to embed.
        xmp_namespace_uri:    URI for the custom XMP namespace used to store
                              unrouted sensor and project fields.  Defaults to
                              "https://soi-frame-extractor.org/xmp/v1/".
        xmp_namespace_prefix: Prefix for the custom XMP namespace.
                              Defaults to "sfe".

    Raises:
        FileNotFoundError: if path does not exist.
        ValueError: if the image format cannot carry the required metadata.
    """
    pass


def _write_exif(path: Path, meta: FrameMetadata) -> None:
    """Write EXIF tags derived from FrameMetadata into the image at path.

    Longitude is normalised to −180/+180 before conversion.  All GPS values
    are passed as absolute magnitudes; hemisphere is encoded in Ref tags.

    Tags written (where values are present):
        DateTimeOriginal        — from utc_timestamp
        GPSDateStamp            — date portion of utc_timestamp
        GPSTimeStamp            — time portion of utc_timestamp
        GPSLatitude             — abs(latitude) as DMS rational via _decimal_to_dms
        GPSLatitudeRef          — "N" or "S" via _decimal_to_ref
        GPSLongitude            — abs(longitude) as DMS rational via _decimal_to_dms
        GPSLongitudeRef         — "E" or "W" via _decimal_to_ref
        GPSAltitude             — depth value as rational (positive magnitude)
        GPSAltitudeRef          — 1 (below sea level)
        Make                    — from project_metadata camera_make
        Model                   — from project_metadata camera_model

    Args:
        path: path to the image file.
        meta: FrameMetadata supplying utc_timestamp, sensor_snapshot,
              and project_metadata.
    """
    pass


def _write_iptc(path: Path, meta: FrameMetadata) -> None:
    """Write IPTC IIM fields derived from project_metadata into the image.

    GPS coordinates are NOT written to IPTC — IIM Record 2 has no GPS fields.

    Fields written (where values are present in project_metadata):
        Credit                  — credit
        Source                  — source
        CopyrightNotice         — copyright
        Caption-Abstract        — caption
        DateCreated             — date portion of utc_timestamp
        TimeCreated             — time portion of utc_timestamp

    Args:
        path: path to the image file.
        meta: FrameMetadata supplying utc_timestamp and project_metadata.
    """
    pass


def _write_xmp(
    path: Path,
    meta: FrameMetadata,
    xmp_namespace_uri: str,
    xmp_namespace_prefix: str,
) -> None:
    """Write XMP properties derived from FrameMetadata into the image.

    Standard XMP properties written:
        xmp:CreateDate          — from utc_timestamp (ISO 8601)
        xmp:MetadataDate        — current wall-clock time (ISO 8601)

    Custom namespace properties written (URI and prefix supplied by caller):
        All keys in sensor_snapshot not routed elsewhere by FIELD_REGISTRY.
        All keys in project_metadata not routed elsewhere by FIELD_REGISTRY.

    Args:
        path:                 path to the image file.
        meta:                 FrameMetadata supplying utc_timestamp,
                              sensor_snapshot, and project_metadata.
        xmp_namespace_uri:    URI registered for the custom namespace.
        xmp_namespace_prefix: prefix used when writing custom namespace properties.
    """
    pass


def _write_ifdo(path: Path, meta: FrameMetadata) -> None:
    """Write iFDO v2.1.0 fields derived from FrameMetadata into the image.

    Longitude is normalised to −180/+180 before writing.  iFDO stores
    coordinates as signed decimal degrees (negative = S or W).

    iFDO data is serialised as a JSON object and embedded in XMP under the
    iFDO namespace.  Fields written (where values are present):

        image-uuid              — generated at write time (UUID4)
        image-datetime          — utc_timestamp as ISO 8601
        image-latitude          — signed decimal degrees from sensor_snapshot
        image-longitude         — signed decimal degrees (normalised to −180/+180)
        image-depth             — from sensor_snapshot depth
        image-altitude-meters   — from sensor_snapshot altitude if present
        image-heading           — from sensor_snapshot heading if present
        image-pitch             — from sensor_snapshot pitch if present
        image-roll              — from sensor_snapshot roll if present
        image-sequence-name     — from project_metadata cruise_id
        image-deployment-id     — from project_metadata dive_id
        image-platform          — nested object: {name: project_metadata vehicle}
        image-pi                — nested object: {name: pi_name, orcid: pi_orcid}
        image-abstract          — from project_metadata project
        image-license           — from project_metadata license

    Args:
        path: path to the image file.
        meta: FrameMetadata supplying utc_timestamp, sensor_snapshot,
              and project_metadata.
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
