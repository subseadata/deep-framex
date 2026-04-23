"""Timestamp parsing utilities

Helpers for building the file list that assemble_biigle_records expects:
a list of (filename, utc_timestamp) pairs.

There are three common ways to supply this input:

1.  Filename produced by this tool's extraction pipeline
    Use parse_filename_template with the same template string used for output.
    The {utc} placeholder in the template locates and parses the timestamp.
    Example: files named "{dive_id}_{utc}.jpg" parsed with the same string.

2.  Separate CSV with filename and timestamp columns
    Use parse_file_list_csv to read the whole list at once.
    Example CSV:
        filename,timestamp
        image001.jpg,2023-12-01T14:30:22.456Z
        image002.jpg,2023-12-01T14:30:25.102Z

3.  Any other source (database query, EXIF read, manual list, etc.)
    Build list[tuple[str, datetime]] directly and pass to assemble_biigle_records.
"""

import csv
import re
from datetime import datetime, timezone
from pathlib import Path


# Regex matching all accepted UTC timestamp variants embedded in filenames:
#   20251115T102530123456  — microseconds (ffffff), output format
#   20251115T102530123     — milliseconds (fff)
#   20251115T102530        — seconds only
_UTC_REGEX = r"(?P<utc>\d{8}T\d{6}(?:\d{3}(?:\d{3})?)?)"


def _parse_utc_string(utc_str: str) -> datetime:
    """Parse a UTC string matched by _UTC_REGEX into a timezone-aware datetime.

    Selects the format by string length to avoid a Python strptime quirk:
    when %S%f are adjacent with no separator and the string has no subsecond
    digits, strptime backtracks and consumes only 1 digit for %S, giving a
    wrong result.  Choosing the format explicitly avoids this.

    Expected lengths:
        15  YYYYMMDDTHHMMSS        (seconds only)
        18  YYYYMMDDTHHMMSSfff     (milliseconds)
        21  YYYYMMDDTHHMMSSffffff  (microseconds)

    Raises:
        ValueError: if the string length is not one of the above.
    """
    fmt = "%Y%m%dT%H%M%S%f" if len(utc_str) > 15 else "%Y%m%dT%H%M%S"
    try:
        return datetime.strptime(utc_str, fmt).replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError(
            f"Cannot parse UTC string '{utc_str}'. "
            f"Expected YYYYMMDDTHHMMSSffffff, YYYYMMDDTHHMMSSfff, or YYYYMMDDTHHMMSS."
        ) from None


def _template_to_regex(template: str) -> re.Pattern:
    """Convert an output filename template string to a compiled regex.

    {utc} is matched with a precise pattern for the known output format.
    All other {key} placeholders are matched as non-greedy wildcards.
    Literal characters in the template are regex-escaped.

    Args:
        template: filename template string, with or without extension.
                  Extension is stripped before matching against the stem.

    Returns:
        Compiled regex with a named 'utc' capture group.

    Raises:
        ValueError: if the template contains no {utc} placeholder.
    """
    # Work on the stem only — strip extension from template if present
    stem = Path(template).stem if "." in template else template

    if "{utc}" not in stem:
        raise ValueError(
            f"Template '{template}' has no {{utc}} placeholder. "
            "The filename must contain {utc} to parse a timestamp from it."
        )

    # Split on {key} or {key:format_spec} placeholders.
    # Capturing only \w+ extracts the key name; [^}]* consumes any format spec.
    # Parts alternate: literal, key, literal, key, ...
    parts = re.split(r"\{(\w+)[^}]*\}", stem)
    regex_parts = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            regex_parts.append(re.escape(part))     # literal text
        elif part == "utc":
            regex_parts.append(_UTC_REGEX)      # precise UTC capture
        else:
            regex_parts.append("(?:.+?)")       # wildcard — value never read

    return re.compile("^" + "".join(regex_parts) + "$")


def parse_filename_template(
    path: Path,
    template: str,
) -> datetime:
    """Parse a UTC datetime from a filename using the output template syntax.

    Accepts the same template string used for filename_template in the
    extraction spec, so files written by this tool can be read back using
    the same string that named them.  The {utc} placeholder locates the
    timestamp; other {key} placeholders in the template are matched as
    wildcards and ignored.

    The {utc} format is fixed: YYYYMMDDTHHMMSSffffff (e.g. 20251115T102530123456),
    which is what the extraction pipeline writes.  Only files produced by
    this tool (or files manually named in that format) will parse correctly.
    For other timestamp formats, use parse_file_list_csv instead.

    Args:
        path:     path to the image file.  Only the stem is used; the file
                  need not exist on disk.
        template: output filename template string, e.g. "{dive_id}_{utc}"
                  or "{cruise_id}_{video_stem}_{utc}.jpg".
                  Must contain a {utc} placeholder.

    Returns:
        timezone-aware datetime in UTC.

    Raises:
        ValueError: if the template has no {utc} placeholder.
        ValueError: if the filename stem does not match the template.

    Example:
        For files produced with filename_template: "{dive_id}_{utc}.jpg":

            from pathlib import Path
            from deep_framex.utils.timestamps import parse_filename_template

            files = [
                (p.name, parse_filename_template(p, "{dive_id}_{utc}"))
                for p in sorted(Path("frames/").glob("*.jpg"))
            ]
    """
    pattern = _template_to_regex(template)
    match = pattern.match(path.stem)
    if not match:
        raise ValueError(
            f"Filename '{path.name}' does not match template '{template}'. "
            f"Expected a filename containing a UTC timestamp in the format "
            f"YYYYMMDDTHHMMSSffffff (e.g. 20251115T102530123456)."
        )
    return _parse_utc_string(match.group("utc"))


def parse_file_list_csv(
    csv_path: Path,
    filename_col: str = "filename",
    timestamp_col: str = "timestamp",
) -> list[tuple[str, datetime]]:
    """Read a CSV file mapping filenames to UTC timestamps.

    Use this when your images have generic names (image001.jpg, etc.) and
    timestamps are recorded separately in a CSV rather than encoded in the
    filename.  The returned list can be passed directly to
    assemble_biigle_records.

    Timestamps are parsed with datetime.fromisoformat, which accepts a wide
    range of ISO 8601 formats including:
        2023-12-01T14:30:22
        2023-12-01T14:30:22.456
        2023-12-01T14:30:22.456Z
        2023-12-01T14:30:22+00:00

    All timestamps are returned as timezone-aware UTC datetimes.  Timestamps
    without timezone info (no Z or offset) are assumed to be UTC.

    Args:
        csv_path:      path to the CSV file.
        filename_col:  name of the column containing image filenames.
                       Default: "filename".
        timestamp_col: name of the column containing UTC timestamps.
                       Default: "timestamp".

    Returns:
        list of (filename, utc_datetime) pairs, in CSV row order.

    Raises:
        FileNotFoundError: if csv_path does not exist.
        KeyError:          if filename_col or timestamp_col is not found in
                           the CSV header.
        ValueError:        if a timestamp value cannot be parsed.

    Example CSV (file_list.csv):
        filename,timestamp
        image001.jpg,2023-12-01T14:30:22.456Z
        image002.jpg,2023-12-01T14:30:25.102Z
        image003.jpg,2023-12-01T14:30:27.891Z

    Example usage:
        from pathlib import Path
        from deep_framex.utils.timestamps import parse_file_list_csv
        from deep_framex.metadata.assemble import assemble_biigle_records
        from deep_framex.metadata.biigle import write_biigle_manifest
        from deep_framex.models.core import ColumnMappings

        files = parse_file_list_csv(Path("file_list.csv"))

        records = assemble_biigle_records(
            files=files,
            csv_path=Path("sensors.csv"),
            mappings=ColumnMappings(
                timestamp="Timestamp",
                latitude="Lat_ddeg",
                longitude="Lon_ddeg",
                depth="Depth_m",
            ),
        )

        write_biigle_manifest(records, Path("output/"))
    """
    files: list[tuple[str, datetime]] = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None or filename_col not in reader.fieldnames:
            raise KeyError(
                f"Column '{filename_col}' not found in {csv_path.name}. "
                f"Available columns: {list(reader.fieldnames or [])}. "
                f"Use the filename_col argument to specify the correct column name."
            )
        if timestamp_col not in reader.fieldnames:
            raise KeyError(
                f"Column '{timestamp_col}' not found in {csv_path.name}. "
                f"Available columns: {list(reader.fieldnames)}. "
                f"Use the timestamp_col argument to specify the correct column name."
            )

        for row in reader:
            dt = datetime.fromisoformat(row[timestamp_col])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            files.append((row[filename_col], dt))

    return files
