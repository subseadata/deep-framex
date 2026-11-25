"""Along-track distance utilities

Pure functions for cumulative distance along a sequence of navigation fixes.
No database, metadata, or video dependencies; safe to import from any module.

The metric is 2D great-circle distance in metres, computed with the Haversine
formula on a sphere of IUGG mean Earth radius.  Depth is deliberately not part
of the metric: a vehicle that holds position while descending has travelled
0 m along track.

Longitude may be -180/+180 or 0-360: the formula sees longitude only through
sin² of half the difference, which repeats every 360°, so both give the same
distance, including across the antimeridian.
"""

from math import asin, cos, radians, sin, sqrt
from typing import Iterable

# IUGG mean Earth radius, metres.
EARTH_RADIUS_M = 6_371_008.8


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in metres.

    Args:
        lat1: latitude of the first point in decimal degrees (-90 to 90).
        lon1: longitude of the first point in decimal degrees, -180/+180 or 0-360.
        lat2: latitude of the second point in decimal degrees.
        lon2: longitude of the second point in decimal degrees, -180/+180 or 0-360.

    Returns:
        Distance in metres.  0.0 for identical points.
    """
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = radians(lon2 - lon1)

    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    # asin() is well conditioned for the short arcs a dive log produces; the
    # clamp guards against a rounding error pushing a slightly above 1.
    return 2 * EARTH_RADIUS_M * asin(min(1.0, sqrt(a)))


def cumulative_distance(rows: Iterable[tuple[float, float]]) -> list[float]:
    """Cumulative along-track distance for a sequence of fixes.

    The first fix is 0 m and every later fix carries the total distance travelled
    from the first, so the result is non-decreasing.  Repeated positions add
    nothing: a stationary vehicle's distance stays flat until it moves again.

    Args:
        rows: (latitude, longitude) tuples in the order travelled.

    Returns:
        One cumulative distance in metres per input row, in the same order.
        Empty list for empty input.
    """
    totals: list[float] = []
    running = 0.0
    previous: tuple[float, float] | None = None

    for lat, lon in rows:
        if previous is not None:
            running += haversine_m(previous[0], previous[1], lat, lon)
        totals.append(running)
        previous = (lat, lon)

    return totals
