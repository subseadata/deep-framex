"""Session database

Manages a per-run SQLite instance (in-memory) that holds sensor readings
and the frame plan for a single extraction session.

Two tables:

    sensor_readings  — one row per sensor observation from the imported CSV.
                       Schema is created dynamically from CSV column names at
                       import time; the timestamp column is always the primary
                       key (stored as Unix epoch float for efficient range
                       queries during planning).

    frame_plan       — one row per frame to extract.  Populated by the planner
                       after applying interval, period, and sensor constraints.
                       Updated by the extractor and metadata writer as work
                       progresses.  Carries a sensor_snapshot JSON blob so
                       downstream stages never need to re-query sensor_readings.

The database is created at the start of an extraction run and discarded when
the run completes or fails.  Nothing here is persisted between runs.
"""

import sqlite3


def create_session_db() -> sqlite3.Connection:
    """Create and return an in-memory SQLite connection for one extraction session.

    Returns:
        An open sqlite3.Connection backed by ':memory:'.  The caller is
        responsible for closing it via close_session_db when the session ends.
    """
    return sqlite3.connect(":memory:")


def init_sensor_table(conn: sqlite3.Connection, columns: list[str]) -> None:
    """Create the sensor_readings table with a schema derived from the CSV columns.

    The timestamp column is always the primary key, named 'timestamp' in the
    database regardless of the original CSV column name.  The importer maps
    the user's timestamp column to this fixed name at insert time.  Every
    column in columns is added as REAL NOT NULL.  Column names are taken
    verbatim from ImportedDataset.columns and have already been validated as
    legal SQL identifiers by the importer.

    Args:
        conn:    active session database connection.
        columns: sensor column names to create, excluding the timestamp column.

    Raises:
        sqlite3.OperationalError: if the table already exists.
    """
    sensor_cols = "".join(f', "{col}" REAL NOT NULL' for col in columns)
    conn.execute(f"""
        CREATE TABLE sensor_readings (
            timestamp REAL PRIMARY KEY
            {sensor_cols}
        )
    """)


def init_frame_plan_table(conn: sqlite3.Connection) -> None:
    """Create the frame_plan table with a fixed schema.

    Columns:
        id              INTEGER PRIMARY KEY AUTOINCREMENT
        utc_timestamp   TEXT NOT NULL   — ISO 8601 UTC of the planned frame
        video_path      TEXT NOT NULL   — absolute path to the source video
        offset_s        REAL NOT NULL   — seconds from t=0 in that video
        status          TEXT NOT NULL   — 'planned' | 'extracted' | 'written'
        sensor_snapshot TEXT            — JSON object of interpolated sensor
                                          values at this timestamp; NULL if no
                                          sensor data was imported

    Args:
        conn: active session database connection.

    Raises:
        sqlite3.OperationalError: if the table already exists.
    """
    conn.execute("""
        CREATE TABLE frame_plan (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            utc_timestamp   TEXT NOT NULL,
            video_path      TEXT NOT NULL,
            offset_s        REAL NOT NULL,
            status          TEXT NOT NULL,
            sensor_snapshot TEXT
        )
    """)


def close_session_db(conn: sqlite3.Connection) -> None:
    """Close the session database connection, discarding all in-memory data.

    Args:
        conn: the connection returned by create_session_db.
    """
    conn.close()
