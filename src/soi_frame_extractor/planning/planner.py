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

import json
import sqlite3
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..db.session_db import init_frame_plan_table
from ..models.models import (
    ExtractionRule,
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
    init_frame_plan_table(conn)

    # Collect all timestamps across rules — set deduplicates across rules
    all_timestamps: set[datetime] = set()
    for rule in spec.rules:
        windows = _rule_windows(rule, session, conn)
        all_timestamps.update(
            _sample_timestamps(windows, rule.interval_s, spec.initial_offset_s)
        )

    # Check once whether sensor data is available
    sensor_cols = _sensor_columns(conn)

    video_offsets: dict[Path, list[float]] = {}
    frame_plan_rows = []

    for utc in sorted(all_timestamps):
        try:
            vf, offset_s = _assign_to_video(utc, session)
        except ValueError:
            warnings.warn(
                f"Sampling interval hit a gap in the video session — "
                f"no frame extracted at {utc.isoformat()}. "
                "Check for missing video files or adjust initial_offset_s.",
                UserWarning,
                stacklevel=2,
            )
            continue
        video_offsets.setdefault(vf.path, []).append(offset_s)

        snapshot = _interpolate_sensor(utc.timestamp(), sensor_cols, conn) if sensor_cols else {}
        frame_plan_rows.append((
            utc.isoformat(),
            str(vf.path),
            offset_s,
            "planned",
            json.dumps(snapshot) if snapshot else None,
        ))

    conn.executemany(
        "INSERT INTO frame_plan (utc_timestamp, video_path, offset_s, status, sensor_snapshot) "
        "VALUES (?,?,?,?,?)",
        frame_plan_rows,
    )
    conn.commit()

    # Return one plan per video that has at least one frame, in session order
    return [
        VideoExtractionPlan(video_file=vf, offsets_s=sorted(video_offsets[vf.path]))
        for vf in session.videos
        if vf.path in video_offsets
    ]


def _rule_windows(
    rule: ExtractionRule,
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
    session_start = session.videos[0].utc_start
    session_end = session.videos[-1].utc_start + session.videos[-1].duration

    # Use explicit periods if provided, otherwise the full session span
    windows: list[TimePeriod] = (
        list(rule.periods)
        if rule.periods
        else [TimePeriod(start=session_start, end=session_end)]
    )

    # Intersect with each constraint's qualifying windows in turn.
    # Short-circuit if nothing remains — no frames possible for this rule.
    for constraint in rule.constraints:
        windows = _intersect_windows(windows, _constraint_windows(constraint, conn))
        if not windows:
            break

    return windows


def _constraint_windows(
    constraint: ExtractionRule.SensorConstraint,
    conn: sqlite3.Connection,
) -> list[TimePeriod]:
    """Query sensor_readings for contiguous time ranges where a constraint is met.

    Scans the sensor_readings table in timestamp order.  Each row is tested
    against the constraint bounds; consecutive qualifying rows are grouped into
    a single TimePeriod whose start and end are the first and last qualifying
    timestamps in that run.

    Args:
        constraint: an ExtractionRule.SensorConstraint with column, min, max.
        conn:       session database connection.

    Returns:
        List of TimePeriod covering the ranges where the constraint is met.

    Raises:
        ValueError: if sensor_readings does not exist (no CSV was imported).
        ValueError: if constraint.column is not a column in sensor_readings.
    """
    table_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='sensor_readings'"
    ).fetchone()
    if not table_exists:
        raise ValueError(
            f"Constraint on column {constraint.column!r} requires sensor data, "
            "but no CSV was imported. Provide a --data CSV or remove the constraint."
        )

    available = [
        row[1]
        for row in conn.execute("PRAGMA table_info(sensor_readings)").fetchall()
        if row[1] != "timestamp"
    ]
    if constraint.column not in available:
        raise ValueError(
            f"Constraint column {constraint.column!r} not found in sensor data. "
            f"Available columns: {available}"
        )

    rows = conn.execute(
        f'SELECT timestamp, "{constraint.column}" FROM sensor_readings ORDER BY timestamp'
    ).fetchall()

    windows = []
    window_start: float | None = None
    last_qualifying: float | None = None

    for ts, val in rows:
        qualifies = (
            (constraint.min is None or val >= constraint.min)
            and (constraint.max is None or val <= constraint.max)
        )
        if qualifies:
            if window_start is None:
                window_start = ts
            last_qualifying = ts
        elif window_start is not None:
            assert last_qualifying is not None  # always set together with window_start
            windows.append(TimePeriod(
                start=datetime.fromtimestamp(window_start, tz=timezone.utc),
                end=datetime.fromtimestamp(last_qualifying, tz=timezone.utc),
            ))
            window_start = None
            last_qualifying = None

    # Close any window still open at the end of the data
    if window_start is not None:
        assert last_qualifying is not None  # always set together with window_start
        windows.append(TimePeriod(
            start=datetime.fromtimestamp(window_start, tz=timezone.utc),
            end=datetime.fromtimestamp(last_qualifying, tz=timezone.utc),
        ))

    return windows


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
    result = []
    for wa in a:
        for wb in b:
            start = max(wa.start, wb.start)
            end = min(wa.end, wb.end)
            if start < end:
                result.append(TimePeriod(start=start, end=end))
    return sorted(result, key=lambda w: w.start)


def _sample_timestamps(
    windows: list[TimePeriod],
    interval_s: float,
    initial_offset_s: float = 0.0,
) -> list[datetime]:
    """Sample UTC timestamps at interval_s across a list of time windows.

    Walks each window from its start plus initial_offset_s, emitting a
    timestamp every interval_s seconds until the window end is reached.
    Does not carry remainder across window boundaries — each window starts
    fresh at its own start plus the offset.

    Each step is computed as window.start + initial_offset_s + n*interval_s
    rather than accumulated additions, avoiding floating-point drift over
    long sessions.

    Args:
        windows:          list of TimePeriod to sample within.
        interval_s:       sampling interval in seconds.
        initial_offset_s: shift the first sample this many seconds from
                          each window start.  Defaults to 0.

    Returns:
        Sorted list of datetime timestamps.
    """
    timestamps = []
    for window in windows:
        n = 0
        while True:
            t = window.start + timedelta(seconds=initial_offset_s + n * interval_s)
            if t > window.end:
                break
            timestamps.append(t)
            n += 1
    return timestamps


def _sensor_columns(conn: sqlite3.Connection) -> list[str]:
    """Return sensor column names (excluding timestamp) if the table exists.

    Returns an empty list if sensor_readings does not exist, meaning no CSV
    was imported and sensor snapshots will be empty for all frames.
    """
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='sensor_readings'"
    ).fetchone()
    if not exists:
        return []
    return [
        row[1]
        for row in conn.execute("PRAGMA table_info(sensor_readings)").fetchall()
        if row[1] != "timestamp"
    ]


def _interpolate_sensor(
    ts: float,
    sensor_cols: list[str],
    conn: sqlite3.Connection,
) -> dict[str, float]:
    """Linearly interpolate all sensor columns at a Unix epoch timestamp.

    Fetches the nearest row at or before ts and the nearest row at or after
    ts, then interpolates between them.  If only one side is available (ts
    is before or after all sensor data) the nearest row's values are used
    as-is rather than extrapolating.

    Args:
        ts:          target timestamp as Unix epoch float.
        sensor_cols: list of sensor column names to interpolate.
        conn:        session database connection.

    Returns:
        Dict mapping each sensor column name to its interpolated value.
    """
    col_list = ", ".join(f'"{c}"' for c in sensor_cols)

    before = conn.execute(
        f"SELECT timestamp, {col_list} FROM sensor_readings "
        "WHERE timestamp <= ? ORDER BY timestamp DESC LIMIT 1",
        (ts,),
    ).fetchone()

    after = conn.execute(
        f"SELECT timestamp, {col_list} FROM sensor_readings "
        "WHERE timestamp >= ? ORDER BY timestamp ASC LIMIT 1",
        (ts,),
    ).fetchone()

    if before is None and after is None:
        return {}
    if before is None:
        return {col: float(after[i + 1]) for i, col in enumerate(sensor_cols)}  # type: ignore[index]
    if after is None:
        return {col: float(before[i + 1]) for i, col in enumerate(sensor_cols)}
    if before[0] == after[0]:
        # Exact match — no interpolation needed
        return {col: float(before[i + 1]) for i, col in enumerate(sensor_cols)}

    t0, t1 = before[0], after[0]
    alpha = (ts - t0) / (t1 - t0)
    return {
        col: before[i + 1] + alpha * (after[i + 1] - before[i + 1])
        for i, col in enumerate(sensor_cols)
    }


def _assign_to_video(
    utc: datetime,
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
    for vf in session.videos:
        end = vf.utc_start + vf.duration
        if vf.utc_start <= utc < end:
            return vf, (utc - vf.utc_start).total_seconds()

    # Handle a timestamp exactly at the end of the last video — the sampler
    # can emit this when the session end falls on an interval boundary.
    last = session.videos[-1]
    session_end = last.utc_start + last.duration
    if utc == session_end:
        return last, last.duration.total_seconds()

    raise ValueError(
        f"Timestamp {utc.isoformat()} falls outside the session span "
        f"({session.videos[0].utc_start.isoformat()} – {session_end.isoformat()})."
    )
