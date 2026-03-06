"""Frame writer

Saves extracted frames to disk as image files.

Filenames are generated from a user-supplied template string defined in the
YAML spec under filename_template.  The template is a standard Python format
string and may reference any of the following variables:

    {utc}          — UTC timestamp, compact format: 20251115T102530123456
    {video_stem}   — source video filename without extension
    {offset_s}     — offset in seconds from the start of the source video
    {<key>}        — any canonical sensor key (e.g. {depth}, {latitude}, {temperature})
    {<key>}        — any key from project_metadata (e.g. {dive_id}, {cruise_id})

Sensor keys use canonical names (the left-hand side of the mappings block in
the YAML spec), not the original CSV column names.  So if the user mapped
"depth: z" in their spec, the template variable is {depth}, not {z}.

Users include only the variables they want.  Any sensor column or metadata
field can be used or omitted freely.

Examples:
    {dive_id}_{depth}m_T{utc}.jpg           — depth + dive ID
    {latitude}_{longitude}_{utc}.tif        — location-stamped, lossless
    {cruise_id}_{video_stem}_{utc}.jpg      — cruise + source video
    frame_{utc}_{offset_s:.1f}s.jpg         — offset with one decimal place

The file extension is taken from the template string.  If no template is
supplied the default pattern is used:

    {utc}_{video_stem}.jpg

Template validation:
    validate_filename_template should be called once at pipeline startup,
    before any frames are extracted.  It renders the template against a dummy
    context of all known keys and raises ValueError with a clear message
    (including a "did you mean?" suggestion) if a key is unknown or the
    syntax is invalid.  This ensures the user gets an immediate, actionable
    error rather than discovering the problem after extraction completes.

    Individual frames may still fall back to the default at render time if a
    sensor value is absent for a specific timestamp (a data gap, not a config
    error).  This per-frame fallback is silent.

The output directory is created if it does not exist.  No collision detection
is performed — include {utc} in the template (strongly recommended) since the
planner guarantees unique timestamps.  Templates that omit {utc} may produce
collisions if sensor values repeat across frames.
"""

import difflib
import io
import struct
import sys
from pathlib import Path

from PIL import Image

from ..metadata.apply_metadata import _build_exif, _build_iptc, _build_xmp
from ..models.models import ExtractedFrame, FrameMetadata

_DEFAULT_TEMPLATE = "{utc}_{video_stem}.jpg"

# Fixed keys always available in the template context, regardless of sensor data.
_BUILTIN_KEYS = {"utc", "video_stem", "offset_s"}


def write_frame(
    frame: ExtractedFrame,
    output_dir: Path,
    filename_template: str | None,
    xmp_namespace_uri: str,
    xmp_namespace_prefix: str,
) -> tuple[Path, FrameMetadata]:
    """Write a single frame to disk with all metadata embedded in one save.

    Renders a filename, builds EXIF, IPTC, and XMP blocks via the metadata
    builders in apply_metadata, then saves the image once via Pillow with
    all metadata included.  output_dir must already exist.

    Returns the path and metadata only — the pixel data is written to disk and
    can be discarded.  The returned FrameMetadata is sufficient for the caller
    to build an iFDO manifest without holding pixel arrays in memory.

    No collision detection is performed.  Include {utc} in the template
    (strongly recommended) — the planner guarantees unique timestamps, so {utc}
    guarantees unique filenames.  Templates that omit {utc} may produce
    collisions if sensor values repeat across frames.

    NOTE for cloud output: this function writes to a local output_dir.  For
    writing directly to S3 or GCS, replace the Pillow save call with an
    upload to the target bucket.  The rest of the function (filename rendering,
    metadata building) is storage-agnostic.

    Args:
        frame:                ExtractedFrame to write.
        output_dir:           directory to write the image file into.  Must exist.
        filename_template:    Python format string (see module docstring), or
                              None to use the default pattern.
        xmp_namespace_uri:    URI for the custom XMP namespace.
        xmp_namespace_prefix: prefix for the custom XMP namespace.

    Returns:
        (Path, FrameMetadata) — path to the written file and its metadata.

    Raises:
        OSError: if the file cannot be written.
    """
    meta = frame.metadata
    filename = _render_filename(frame, filename_template)
    path = output_dir / filename

    exif_bytes = _build_exif(meta)
    iptc_bytes = _build_iptc(meta)
    xmp_bytes = _build_xmp(meta, xmp_namespace_uri, xmp_namespace_prefix)

    img = Image.fromarray(frame.frame)

    suffix = path.suffix.lower()
    if suffix in (".tif", ".tiff"):
        # TIFF: embed EXIF only; IPTC/XMP in TIFF requires tiffinfo tag injection
        # (tags 33723 and 700 respectively) — not yet implemented.
        img.save(path, format="TIFF", exif=exif_bytes)
    else:
        # JPEG: save with EXIF, then inject XMP and IPTC segments into the byte stream.
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95, exif=exif_bytes)
        jpeg_data = _inject_jpeg_segments(buf.getvalue(), iptc_bytes, xmp_bytes)
        path.write_bytes(jpeg_data)

    return path, meta


def output_frames(
    frames: list[ExtractedFrame],
    output_dir: Path,
    filename_template: str | None = None,
    xmp_namespace_uri: str = "https://soi-frame-extractor.org/xmp/v1/",
    xmp_namespace_prefix: str = "sfe",
) -> list[tuple[Path, FrameMetadata]]:
    """Write a list of extracted frames to disk and return paths with metadata.

    Creates output_dir if it does not exist.  Delegates each write to
    write_frame, which embeds all metadata (EXIF, IPTC, XMP) in a single
    Pillow save per frame.

    Returns (Path, FrameMetadata) pairs — pixel data is written and discarded.
    The returned list is sufficient for building an iFDO manifest.

    No collision detection is performed.  Include {utc} in the filename
    template to guarantee unique filenames — see write_frame for details.

    Args:
        frames:               list of ExtractedFrame objects to write.
        output_dir:           directory to write image files into.
        filename_template:    Python format string (see module docstring).
                              If None, the default pattern is used.
        xmp_namespace_uri:    URI for the custom XMP namespace.
        xmp_namespace_prefix: prefix for the custom XMP namespace.

    Returns:
        List of (Path, FrameMetadata) pairs in input order.

    Raises:
        OSError: if output_dir cannot be created or a file cannot be written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    return [
        write_frame(frame, output_dir, filename_template, xmp_namespace_uri, xmp_namespace_prefix)
        for frame in frames
    ]


def validate_filename_template(
    template: str,
    sensor_keys: list[str],
    metadata_keys: list[str],
) -> None:
    """Validate a filename template against the known set of available keys.

    Should be called once at pipeline startup, before any frames are extracted.
    Renders the template against a dummy context populated with all known keys
    and raises ValueError if any referenced key is absent or the format syntax
    is invalid.

    Unknown key errors include a "did you mean?" suggestion using
    difflib.get_close_matches against the full set of available keys.

    Args:
        template:      filename_template string from ExtractionSpec.
        sensor_keys:   canonical sensor key names — the non-timestamp keys of
                       ColumnMappings (e.g. ["latitude", "depth", "temperature"]).
                       Pass an empty list if no CSV was imported.
        metadata_keys: keys from ExtractionSpec.project_metadata.

    Raises:
        ValueError: if the template contains an unknown key, with a message
                    identifying the bad key and suggesting the closest match.
        ValueError: if the template string is syntactically invalid as a
                    Python format string.
    """
    all_keys = _BUILTIN_KEYS | set(sensor_keys) | set(metadata_keys)
    dummy = {k: "0" for k in all_keys}

    try:
        template.format_map(dummy)
    except KeyError as e:
        bad_key = e.args[0]
        suggestions = difflib.get_close_matches(bad_key, sorted(all_keys), n=1)
        hint = f" (did you mean '{suggestions[0]}'?)" if suggestions else ""
        raise ValueError(
            f"filename_template references unknown key '{bad_key}'{hint}.\n"
            f"Available keys: {sorted(all_keys)}"
        ) from None
    except (ValueError, IndexError) as e:
        raise ValueError(f"filename_template is not a valid format string: {e}") from e


def _render_filename(frame: ExtractedFrame, template: str | None) -> str:
    """Render a filename for a frame from the template string.

    Builds a context dict from the frame's metadata and attempts to render
    the template via str.format_map.  On any failure (missing key, format
    error, bad syntax) warns to stderr and falls back to the default pattern.

    Template context keys available:
        utc         — compact UTC timestamp string (%Y%m%dT%H%M%S%f)
        video_stem  — frame.metadata.video_path.stem
        offset_s    — frame.metadata.offset_s (float)
        + all keys from frame.metadata.sensor_snapshot (float values)
        + all keys from frame.metadata.project_metadata (str values)

    Sensor and project_metadata keys are merged into a flat dict.  If a key
    appears in both, project_metadata wins.

    Args:
        frame:    ExtractedFrame whose metadata provides the context values.
        template: format string from ExtractionSpec.filename_template,
                  or None to use the default.

    Returns:
        Rendered filename string including extension.
    """
    meta = frame.metadata
    context: dict = {}
    context.update(meta.sensor_snapshot)
    context.update(meta.project_metadata)
    context["utc"] = meta.utc_timestamp.strftime("%Y%m%dT%H%M%S%f")
    context["video_stem"] = meta.video_path.stem
    context["offset_s"] = meta.offset_s

    effective = template if template is not None else _DEFAULT_TEMPLATE

    try:
        return effective.format_map(context)
    except (KeyError, ValueError, IndexError):
        if template is not None:
            print(
                f"Warning: filename_template could not be rendered for frame at "
                f"{meta.utc_timestamp.isoformat()}; using default.",
                file=sys.stderr,
            )
        return _DEFAULT_TEMPLATE.format_map(context)


def _inject_jpeg_segments(jpeg_bytes: bytes, iptc_bytes: bytes, xmp_bytes: bytes) -> bytes:
    """Inject IPTC (APP13) and XMP (APP1) segments into a JPEG byte stream.

    Scans past any existing APP markers (0xE0–0xEF) written by Pillow and
    inserts the new segments right after them, before the image data.  This
    gives the expected ordering: EXIF APP1 → XMP APP1 → IPTC APP13 → image.

    Args:
        jpeg_bytes: raw JPEG bytes as returned by Pillow save.
        iptc_bytes: IPTC IIM bytes in Photoshop 3.0 wrapper, or b''.
        xmp_bytes:  serialised XMP packet bytes, or b''.

    Returns:
        JPEG bytes with the new segments injected.
    """
    # Find insertion point: right after all existing APP segments (0xE0–0xEF).
    # Those segments have the structure: FF Ex [2-byte length including itself] [data].
    pos = 2  # skip SOI (FF D8)
    while pos + 3 < len(jpeg_bytes):
        if jpeg_bytes[pos] != 0xFF:
            break
        marker = jpeg_bytes[pos + 1]
        if 0xE0 <= marker <= 0xEF:
            seg_length = struct.unpack(">H", jpeg_bytes[pos + 2 : pos + 4])[0]
            pos += 2 + seg_length
        else:
            break

    segments = b""
    if xmp_bytes:
        xmp_data = b"http://ns.adobe.com/xap/1.0/\x00" + xmp_bytes
        segments += b"\xff\xe1" + struct.pack(">H", len(xmp_data) + 2) + xmp_data
    if iptc_bytes:
        segments += b"\xff\xed" + struct.pack(">H", len(iptc_bytes) + 2) + iptc_bytes

    if not segments:
        return jpeg_bytes
    return jpeg_bytes[:pos] + segments + jpeg_bytes[pos:]
