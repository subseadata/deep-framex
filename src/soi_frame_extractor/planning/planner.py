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
import math
import sqlite3
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

from ..db.session_db import init_frame_plan_table
from ..models.models import (
    ExtractionRule,
    ExtractionSpec,
    FrameSpec,
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

    # The grid anchor is fixed for the whole session.
    # initial_offset_s shifts it forward from the first video's first frame.
    # Every rule samples from this same anchor — constraint windows are filters
    # on the global grid, not separate grids with their own offsets.
    session_start = session.videos[0].utc_start

    # Use a set so that identical timestamps from different rules appear only once.
    # A timestamp claimed by two overlapping rules is deduplicated here — the
    # extractor will see it once and write one frame.
    all_timestamps: set[datetime] = set()
    for rule in spec.rules:
        windows = _rule_windows(rule, session, conn)
        all_timestamps.update(
            _sample_timestamps(windows, rule.interval_s, session_start, spec.initial_offset_s)
        )

    # Check once here whether sensor data was loaded — avoids repeated database
    # lookups inside the per-frame loop below.
    sensor_cols = sensor_columns(conn)

    # video_frames accumulates FrameSpec objects per video, keeping offset and
    # sensor snapshot together so they can never get out of sync.
    video_frames: dict[Path, list[FrameSpec]] = {}
    frame_plan_rows = []

    for utc in sorted(all_timestamps):
        try:
            vf, offset_s = _assign_to_video(utc, session)
        except ValueError:
            # This timestamp falls in a gap between two video files.
            # Warn the user and skip it — don't abort the whole run.
            warnings.warn(
                f"Sampling interval hit a gap in the video session — "
                f"no frame extracted at {utc.isoformat()}. "
                "Check for missing video files or adjust initial_offset_s.",
                UserWarning,
                stacklevel=2,
            )
            continue

        # Interpolate sensor readings at this exact timestamp.
        snapshot = interpolate_sensor(utc.timestamp(), sensor_cols, conn, spec.interpolation_window) if sensor_cols else {}

        # Keep offset and snapshot together in a FrameSpec — the plan is self-contained
        # and the extractor needs no database access.
        video_frames.setdefault(vf.path, []).append(
            FrameSpec(offset_s=offset_s, sensor_snapshot=snapshot)
        )

        # frame_plan still records progress status for diagnostics and future resume support.
        frame_plan_rows.append((
            utc.isoformat(),
            str(vf.path),
            offset_s,
            "planned",
            json.dumps(snapshot) if snapshot else None,
        ))

    # One bulk INSERT is far faster than one INSERT per frame for large sessions.
    conn.executemany(
        "INSERT INTO frame_plan (utc_timestamp, video_path, offset_s, status, sensor_snapshot) "
        "VALUES (?,?,?,?,?)",
        frame_plan_rows,
    )
    conn.commit()

    # Return one self-contained plan per video that has at least one frame, in session order.
    # Timestamps are processed in sorted(all_timestamps) order, so frames within each
    # video are already in ascending offset order — no secondary sort needed.
    return [
        VideoExtractionPlan(
            video_file=vf,
            frames=video_frames[vf.path],
            project_metadata=spec.project_metadata,
        )
        for vf in session.videos
        if vf.path in video_frames
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

    # Start with the full session as one big window.
    # If the rule names specific time periods, use those instead.
    windows: list[TimePeriod] = (
        list(rule.periods)
        if rule.periods
        else [TimePeriod(start=session_start, end=session_end)]
    )

    # Narrow the windows one constraint at a time.
    # If no windows survive an intersection, stop early — nothing left to sample.
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
    # sensor_readings won't exist if the user didn't supply a data file.
    # Give a clear error rather than letting the missing-table crash bubble up.
    table_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='sensor_readings'"
    ).fetchone()
    if not table_exists:
        raise ValueError(
            f"Constraint on column {constraint.column!r} requires sensor data, "
            "but no CSV was imported. Provide a --data CSV or remove the constraint."
        )

    # PRAGMA table_info() returns one row per column; index 1 is the column name.
    # This lets us check at runtime which columns were actually imported from the CSV.
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

    # Walk every sensor reading in time order.
    # Group consecutive qualifying readings into one TimePeriod each.
    # A reading qualifies when its value is within the constraint's min/max bounds.
    for ts, val in rows:
        qualifies = (
            (constraint.min is None or val >= constraint.min)
            and (constraint.max is None or val <= constraint.max)
        )
        if qualifies:
            if window_start is None:
                window_start = ts          # mark the start of a new qualifying run
            last_qualifying = ts
        elif window_start is not None:
            # This reading broke the run — close the current window and reset.
            assert last_qualifying is not None  # always set together with window_start
            windows.append(TimePeriod(
                start=datetime.fromtimestamp(window_start, tz=timezone.utc),
                end=datetime.fromtimestamp(last_qualifying, tz=timezone.utc),
            ))
            window_start = None
            last_qualifying = None

    # Close any window still open when sensor data runs out.
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
            if start <= end:
                result.append(TimePeriod(start=start, end=end))
    return sorted(result, key=lambda w: w.start)


def _sample_timestamps(
    windows: list[TimePeriod],
    interval_s: float,
    session_start: datetime,
    initial_offset_s: float = 0.0,
) -> list[datetime]:
    """Sample UTC timestamps at interval_s across a list of time windows.

    The sampling grid is anchored to session_start + initial_offset_s and is
    the same for every call — period windows and sensor constraint windows are
    filters on this global grid, not separate grids with their own offsets.
    This means initial_offset_s only shifts from the very start of the session,
    never from the start of a constraint window or time period.

    For each window, the first grid step at or after window.start is found,
    and steps are emitted until window.end is exceeded.  Each step is computed
    as grid_origin + n * interval_s rather than by accumulating additions,
    which prevents floating-point drift over long sessions.

    Args:
        windows:          list of TimePeriod to sample within.
        interval_s:       sampling interval in seconds.
        session_start:    UTC start of the first video; anchors the grid.
        initial_offset_s: shift the grid this many seconds from session_start.
                          Defaults to 0.

    Returns:
        List of datetime timestamps (unsorted — caller deduplicates via set).
    """
    # One fixed origin for the whole session.  All rules share this anchor.
    grid_origin = session_start + timedelta(seconds=initial_offset_s)

    timestamps = []
    for window in windows:
        # How many seconds from the grid origin to the start of this window?
        # If the answer is negative (grid_origin is after window.start, e.g. because
        # initial_offset_s is very large), n_start = 0 and we begin at grid_origin.
        elapsed = (window.start - grid_origin).total_seconds()
        n_start = max(0, math.ceil(elapsed / interval_s))
        n = n_start
        while True:
            t = grid_origin + timedelta(seconds=n * interval_s)
            if t > window.end:
                break
            timestamps.append(t)
            n += 1
    return timestamps


def sensor_columns(conn: sqlite3.Connection) -> list[str]:
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


def interpolate_sensor(
    ts: float,
    sensor_cols: list[str],
    conn: sqlite3.Connection,
    window: int = 2,
) -> dict[str, float]:
    """Interpolate all sensor columns at a Unix epoch timestamp.

    Fetches up to `window` rows on each side of ts, computes the median
    timestamp and median value for each side, then linearly interpolates
    between those two representative points.  Using multiple rows per side
    makes the result robust to single erratic readings.

    Warns (but does not raise) when one side has no rows — meaning the
    frame timestamp is outside the sensor data range and values must be
    extrapolated from the nearest available readings.  Partial windows
    (fewer than `window` rows available but at least one) are used silently.

    Args:
        ts:          target timestamp as Unix epoch float.
        sensor_cols: list of sensor column names to interpolate.
        conn:        session database connection.
        window:      number of rows to use on each side.  Default 2.

    Returns:
        Dict mapping each sensor column name to its interpolated value.
        Empty dict if no sensor rows exist at all.
    """
    col_list = ", ".join(f'"{c}"' for c in sensor_cols)
    utc_str = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

    # Fetch up to `window` rows on each side of the target timestamp.
    # Using several rows makes the result more stable if one reading is a spike or error.
    before_rows = conn.execute(
        f"SELECT timestamp, {col_list} FROM sensor_readings "
        "WHERE timestamp <= ? ORDER BY timestamp DESC LIMIT ?",
        (ts, window),
    ).fetchall()

    after_rows = conn.execute(
        f"SELECT timestamp, {col_list} FROM sensor_readings "
        "WHERE timestamp >= ? ORDER BY timestamp ASC LIMIT ?",
        (ts, window),
    ).fetchall()

    if not before_rows and not after_rows:
        return {}

    if not before_rows:
        # Frame is before all sensor data — no earlier readings to interpolate from.
        # Return the nearest available readings and warn the user.
        warnings.warn(
            f"Frame at {utc_str} is before all sensor data — "
            f"values extrapolated from the {len(after_rows)} nearest reading(s). "
            "Consider using initial_offset_s to shift sampling into the sensor data range.",
            UserWarning,
            stacklevel=3,
        )
        return {col: median(row[i + 1] for row in after_rows) for i, col in enumerate(sensor_cols)}

    if not after_rows:
        # Frame is after all sensor data — same situation in the other direction.
        warnings.warn(
            f"Frame at {utc_str} is after all sensor data — "
            f"values extrapolated from the {len(before_rows)} nearest reading(s). "
            "Ensure sensor logging continues until after the last video ends.",
            UserWarning,
            stacklevel=3,
        )
        return {col: median(row[i + 1] for row in before_rows) for i, col in enumerate(sensor_cols)}

    # Use the median timestamp and median value of each side as representative points.
    # Median is resistant to individual outliers or jitter in sensor logging frequency.
    t_before = median(row[0] for row in before_rows)
    t_after = median(row[0] for row in after_rows)

    if t_before >= t_after:
        # The before and after windows overlap on the same rows — the frame timestamp
        # coincides exactly with a sensor reading.  Deduplicate and take the median.
        unique = list({row[0]: row for row in before_rows + after_rows}.values())
        return {col: median(row[i + 1] for row in unique) for i, col in enumerate(sensor_cols)}

    # Linear interpolation: alpha = 0 means exactly at t_before, alpha = 1 at t_after.
    alpha = (ts - t_before) / (t_after - t_before)
    return {
        col: median(row[i + 1] for row in before_rows)
             + alpha * (median(row[i + 1] for row in after_rows)
                        - median(row[i + 1] for row in before_rows))
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
    # Walk videos in session order (sorted by utc_start).
    # The half-open interval [utc_start, utc_start + duration) means two adjacent
    # videos never both claim the same timestamp.
    for vf in session.videos:
        end = vf.utc_start + vf.duration
        if vf.utc_start <= utc < end:
            return vf, (utc - vf.utc_start).total_seconds()

    # Special case: the sampler can emit a timestamp exactly equal to the session
    # end when the session duration is a perfect multiple of interval_s.
    # The half-open interval above would miss this — accept it on the last video.
    last = session.videos[-1]
    session_end = last.utc_start + last.duration
    if utc == session_end:
        return last, last.duration.total_seconds()

    raise ValueError(
        f"Timestamp {utc.isoformat()} falls outside the session span "
        f"({session.videos[0].utc_start.isoformat()} – {session_end.isoformat()})."
    )
