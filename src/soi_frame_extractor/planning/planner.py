"""Extraction planner

Translates an ExtractionSpec and VideoSession into a list of VideoExtractionPlans —
one per video, each containing the offsets (seconds from t=0) to extract.

Also writes all planned frames into the session database frame_plan table,
with a sensor_snapshot JSON blob of interpolated sensor values at each
timestamp.  Downstream stages read from frame_plan; the extractor uses the
returned VideoExtractionPlan list.

Rule composition:
    Same rule  — periods and constraints are intersected.  Only timestamps
                 where all conditions are simultaneously met are included.
    Across rules — timestamps are unioned and deduplicated.  Each rule
                   contributes independently.
"""

import sqlite3

from ..models.models import (
    ExtractionSpec,
    TimePeriod,
    VideoExtractionPlan,
    VideoFile,
    VideoSession,
)


def plan(
    spec: ExtractionSpec,
    session: VideoSession,
    conn: sqlite3.Connection,
) -> list[VideoExtractionPlan]:
    """Translate an ExtractionSpec into per-video extraction offsets.

    For each rule, resolves the effective time windows by intersecting
    periods and sensor constraint windows, then samples at interval_s.
    Unions all timestamps across rules, deduplicates, writes to frame_plan,
    and maps timestamps to per-video offsets.

    Args:
        spec:    one or more extraction rules with optional periods,
                 constraints, mappings, and project metadata.
        session: ordered list of probed VideoFiles covering the session.
        conn:    active session database connection.  Used to query
                 sensor_readings for constraint windows and to write
                 the resulting frame_plan rows.

    Returns:
        List of VideoExtractionPlan, one per video that has at least one
        frame to extract, ordered by video utc_start.

    Raises:
        ValueError: if a planned timestamp falls outside the span of
                    the session.
        ValueError: if a constraint references a column not present in
                    sensor_readings.
    """
    pass


def _rule_windows(
    rule,
    session: VideoSession,
    conn: sqlite3.Connection,
) -> list[TimePeriod]:
    """Compute the effective time windows for a single extraction rule.

    Starts with the full session span as one window.  If the rule has
    periods, replaces the full session with those periods.  If the rule
    has constraints, queries sensor_readings for windows where each
    constraint is satisfied and intersects those against the current
    windows.  Returns whatever time ranges remain after all intersections.

    Args:
        rule:    an ExtractionRule with optional periods and constraints.
        session: VideoSession used to determine the full session span.
        conn:    session database connection for constraint queries.

    Returns:
        List of TimePeriod representing the effective windows for this
        rule.  Empty list means no frames should be extracted.
    """
    pass


def _constraint_windows(
    constraint,
    conn: sqlite3.Connection,
) -> list[TimePeriod]:
    """Query sensor_readings for contiguous time ranges where a constraint is met.

    Scans the sensor_readings table for rows where constraint.column is
    within [constraint.min, constraint.max] (either bound may be None for
    an open-ended constraint).  Groups consecutive qualifying rows into
    contiguous TimePeriod windows.

    Args:
        constraint: an ExtractionRule.SensorConstraint with column, min, max.
        conn:       session database connection.

    Returns:
        List of TimePeriod covering the ranges where the constraint is met.

    Raises:
        ValueError: if constraint.column is not a column in sensor_readings.
    """
    pass


def _intersect_windows(
    a: list[TimePeriod],
    b: list[TimePeriod],
) -> list[TimePeriod]:
    """Return the intersection of two lists of time windows.

    Compares each window in a against each window in b and retains only
    the overlapping segments.  Order of the result is chronological.

    Args:
        a: first list of TimePeriod windows.
        b: second list of TimePeriod windows.

    Returns:
        List of TimePeriod representing the overlapping segments.
        Empty list if there is no overlap.
    """
    pass


def _sample_timestamps(
    windows: list[TimePeriod],
    interval_s: float,
) -> list:
    """Sample UTC timestamps at interval_s across a list of time windows.

    Walks each window from its start, emitting a timestamp every interval_s
    seconds until the window end is reached.  Does not carry remainder
    across window boundaries — each window starts fresh at its own start.

    Args:
        windows:    list of TimePeriod to sample within.
        interval_s: sampling interval in seconds.

    Returns:
        Sorted list of datetime timestamps.
    """
    pass


def _assign_to_video(
    utc,
    session: VideoSession,
) -> tuple[VideoFile, float]:
    """Find which video contains a UTC timestamp and return its offset.

    Searches the ordered VideoSession for the VideoFile whose span
    contains the given UTC timestamp, then computes the offset in seconds
    from that video's t=0.

    Args:
        utc:     a UTC datetime timestamp to locate.
        session: ordered VideoSession.

    Returns:
        Tuple of (VideoFile, offset_s) for the containing video.

    Raises:
        ValueError: if utc falls outside the span of all videos in the
                    session.
    """
    pass
