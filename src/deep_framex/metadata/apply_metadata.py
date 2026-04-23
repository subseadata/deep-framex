"""Metadata builders for EXIF, IPTC, and XMP layers.

Assembles per-image metadata for extracted frames.  Each build function
returns metadata in the format expected by Pillow at save time, so all
layers are embedded in a single file write — no post-hoc re-opening.

    _build_exif(meta) → bytes   piexif-encoded EXIF block
    _build_iptc(meta) → bytes   raw IPTC IIM block (APP13 Photoshop 3.0 wrapper)
    _build_xmp(meta, ns_uri, ns_prefix) → bytes   serialised XMP packet

iFDO is NOT handled here.  iFDO is a standalone JSON sidecar file written
once per extraction run by metadata/ifdo.py — it is not embedded in image files.

Routing is governed by FIELD_REGISTRY for known fields (latitude, longitude,
depth, credit, source, copyright, caption, camera_make, camera_model).
Any sensor column or project_metadata key not present in FIELD_REGISTRY is
written to XMP under a user-configurable custom namespace.  The namespace
URI and prefix are taken from ExtractionSpec (xmp_namespace_uri,
xmp_namespace_prefix) and default to
"https://deep-framex.org/xmp/v1/" / "dfx".

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

import struct
from datetime import datetime, timezone

import piexif

from ..models.core import FIELD_REGISTRY, FrameMetadata
from ..utils.coordinates import decimal_to_dms, decimal_to_ref, normalize_longitude

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
    ifd0: dict = {}
    exif_ifd: dict = {}
    gps_ifd: dict = {}

    # Timestamp
    dt_str = meta.utc_timestamp.strftime("%Y:%m:%d %H:%M:%S")
    exif_ifd[piexif.ExifIFD.DateTimeOriginal] = dt_str.encode()
    gps_ifd[piexif.GPSIFD.GPSDateStamp] = meta.utc_timestamp.strftime("%Y:%m:%d").encode()
    h = meta.utc_timestamp.hour
    m = meta.utc_timestamp.minute
    s = meta.utc_timestamp.second
    gps_ifd[piexif.GPSIFD.GPSTimeStamp] = [(h, 1), (m, 1), (s, 1)]

    # GPS latitude
    lat = meta.sensor_snapshot.get("latitude")
    if lat is not None:
        gps_ifd[piexif.GPSIFD.GPSLatitude] = decimal_to_dms(abs(lat))
        gps_ifd[piexif.GPSIFD.GPSLatitudeRef] = decimal_to_ref(lat, "lat").encode()

    # GPS longitude (normalise 0–360 → −180/+180 first)
    lon = meta.sensor_snapshot.get("longitude")
    if lon is not None:
        lon = normalize_longitude(lon)
        gps_ifd[piexif.GPSIFD.GPSLongitude] = decimal_to_dms(abs(lon))
        gps_ifd[piexif.GPSIFD.GPSLongitudeRef] = decimal_to_ref(lon, "lon").encode()

    # GPS altitude — depth as positive magnitude, tagged below sea level
    depth = meta.sensor_snapshot.get("depth")
    if depth is not None:
        depth_abs = abs(depth)
        depth_int = round(depth_abs * 100)
        gps_ifd[piexif.GPSIFD.GPSAltitude] = (depth_int, 100)
        gps_ifd[piexif.GPSIFD.GPSAltitudeRef] = b"\x01"

    # Camera make / model from project metadata
    make = meta.project_metadata.get("camera_make")
    if make:
        ifd0[piexif.ImageIFD.Make] = make.encode()
    model = meta.project_metadata.get("camera_model")
    if model:
        ifd0[piexif.ImageIFD.Model] = model.encode()

    exif_dict = {"0th": ifd0, "Exif": exif_ifd, "GPS": gps_ifd}
    return piexif.dump(exif_dict)


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

    Returns an empty bytes object if there are no IPTC fields to write.

    Args:
        meta: FrameMetadata supplying utc_timestamp and project_metadata.

    Returns:
        Raw IPTC IIM bytes wrapped in a Photoshop 3.0 APP13 container,
        ready to inject into a JPEG APP13 segment.  Returns b'' if no
        IPTC fields are present.
    """
    def iim_field(dataset: int, value: str) -> bytes:
        data = value.encode("utf-8")
        return b"\x1c\x02" + bytes([dataset]) + struct.pack(">H", len(data)) + data

    iim = b""

    # Date and time are always written if we have any IPTC content at all.
    # We write them unconditionally alongside any project_metadata fields.
    pm = meta.project_metadata

    if "credit" in pm:
        iim += iim_field(110, pm["credit"])
    if "source" in pm:
        iim += iim_field(115, pm["source"])
    if "copyright" in pm:
        iim += iim_field(116, pm["copyright"])
    if "caption" in pm:
        iim += iim_field(120, pm["caption"])

    if not iim:
        return b""

    # Add date and time when we have other IPTC content
    iim = (
        iim_field(55, meta.utc_timestamp.strftime("%Y%m%d"))
        + iim_field(60, meta.utc_timestamp.strftime("%H%M%S+0000"))
        + iim
    )

    # Wrap in Photoshop 3.0 IRB container for APP13 embedding
    irb_length = struct.pack(">I", len(iim))
    irb = b"8BIM\x04\x04\x00\x00" + irb_length + iim
    if len(iim) % 2:
        irb += b"\x00"  # IRB data must be padded to even length

    return b"Photoshop 3.0\x00" + irb


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
        Serialised XMP packet bytes ready to embed in a JPEG APP1 segment.
    """
    create_date = meta.utc_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p = xmp_namespace_prefix

    lines = []
    for key in _unrouted_sensor_keys(meta):
        val = meta.sensor_snapshot[key]
        lines.append(f"      <{p}:{key}>{val}</{p}:{key}>")
    for key in _unrouted_project_keys(meta):
        val = _xml_escape(meta.project_metadata[key])
        lines.append(f"      <{p}:{key}>{val}</{p}:{key}>")

    custom_block = "\n".join(lines)

    xmp = (
        '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        '  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        '    <rdf:Description rdf:about=""\n'
        '        xmlns:xmp="http://ns.adobe.com/xap/1.0/"\n'
        f'        xmlns:{p}="{xmp_namespace_uri}">\n'
        f"      <xmp:CreateDate>{create_date}</xmp:CreateDate>\n"
        f"      <xmp:MetadataDate>{now}</xmp:MetadataDate>\n"
        + (custom_block + "\n" if custom_block else "")
        + "    </rdf:Description>\n"
        "  </rdf:RDF>\n"
        "</x:xmpmeta>\n"
        '<?xpacket end="w"?>'
    )
    return xmp.encode("utf-8")


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
    return [k for k in meta.sensor_snapshot if k not in FIELD_REGISTRY]


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
    return [k for k in meta.project_metadata if k not in FIELD_REGISTRY]


def _xml_escape(value: str) -> str:
    """Escape special characters for safe embedding in XML text content."""
    return (
        value
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
