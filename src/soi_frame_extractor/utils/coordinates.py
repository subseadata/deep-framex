"""Coordinate conversion utilities

Pure functions for normalising and converting GPS coordinates.
No metadata-layer dependencies; safe to import from any module.

All functions expect and return decimal degrees unless otherwise stated.
Input longitude accepts both −180/+180 and 0–360 conventions.
"""


def normalize_longitude(lon: float) -> float:
    """Normalise a longitude value to the −180/+180 range.

    Accepts both the −180/+180 and 0–360 conventions.  Values already in
    the −180/+180 range are returned unchanged.

    Args:
        lon: longitude in decimal degrees, either −180/+180 or 0–360.

    Returns:
        Longitude in decimal degrees in the range −180 ≤ lon ≤ 180.
    """
    pass


def decimal_to_dms(degrees: float) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    """Convert an absolute decimal-degree value to DMS rational tuples for EXIF.

    Caller must pass the absolute value (no sign); hemisphere direction is
    encoded separately via decimal_to_ref and written to the Ref tag.

    Returns three (numerator, denominator) rational pairs representing
    degrees, minutes, and seconds, suitable for writing to GPSLatitude or
    GPSLongitude with a library such as piexif.

    Args:
        degrees: absolute decimal degrees, i.e. abs(coordinate).

    Returns:
        Tuple of three (int, int) pairs: (deg_num, 1), (min_num, 1),
        (sec_num, 10000) where sec_num is seconds × 10000.
    """
    pass


def decimal_to_ref(value: float, axis: str) -> str:
    """Return the EXIF Ref tag value for a signed coordinate.

    Args:
        value: signed decimal degrees (negative = S or W).
        axis:  "lat" for latitude, "lon" for longitude.

    Returns:
        "N" or "S" for axis="lat"; "E" or "W" for axis="lon".

    Raises:
        ValueError: if axis is not "lat" or "lon".
    """
    pass
