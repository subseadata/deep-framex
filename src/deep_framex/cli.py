"""Command-line interface for deep-framex

Entry point: __main__.py calls main(), which builds the argument parser
and runs either the extraction pipeline or the planning (dry-run) step.

Usage:
    deep-framex <source> --spec <yaml> [--output <dir>]
    deep-framex <source> --spec <yaml> --plan [--data <csv>]

    <source>  — path to a directory of video files, or one or more explicit
                video file paths.  Passed directly to discover_videos, so the
                same rules apply: directory OR list; single bare file raises
                ValueError (wrap it: deep-framex /path/to/file.mp4).
"""

import argparse
import sys
from datetime import timedelta
from pathlib import Path

from .config.spec_parser import spec_from_file
from .config.video_discovery import discover_videos
from .db.session_db import create_session_db, close_session_db
from .data.importer import import_csv
from .extraction.video_session import create_video_session
from .pipeline import extract
from .planning.planner import plan


def cmd_extract(args: argparse.Namespace) -> int:
    """Run the full extraction pipeline from parsed CLI arguments.

    Delegates entirely to pipeline.extract().  Catches known error types,
    logs them to stderr, and returns a non-zero exit code.

    Args:
        args: parsed Namespace from the argument parser, containing:
            - args.source:  list[str] of one or more paths supplied by user
            - args.spec:    Path to the YAML extraction spec
            - args.output:  Path to the output directory for extracted frames
            - args.data:    Path to sensor CSV (optional)

    Returns:
        0 on success, 1 on any handled error (logged to stderr).
    """
    source_paths = [Path(s) for s in args.source]

    # One path that is a directory → pass as Path (directory discovery mode).
    # Anything else (multiple paths, or a single file) → pass as list[Path].
    if len(source_paths) == 1 and source_paths[0].is_dir():
        video_source: Path | list[Path] = source_paths[0]
    else:
        video_source = source_paths

    try:
        extract(
            spec_path=Path(args.spec),
            video_source=video_source,
            output_dir=Path(args.output),
            csv_path=Path(args.data) if args.data else None,
        )
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        return 1


def cmd_plan(args: argparse.Namespace) -> int:
    """Plan extraction without decoding or writing any frames.

    Calls the planning step, prints the planned frames with UTC timestamps,
    and exits.  Useful for validating a spec, checking frame counts, and
    debugging timestamp alignment before running a full extraction.

    Args:
        args: parsed Namespace containing source, spec, data, and output.

    Returns:
        0 on success, 1 on error.
    """
    source_paths = [Path(s) for s in args.source]

    if len(source_paths) == 1 and source_paths[0].is_dir():
        video_source: Path | list[Path] = source_paths[0]
    else:
        video_source = source_paths

    try:
        spec = spec_from_file(Path(args.spec))
        session = create_video_session(discover_videos(video_source))
        conn = create_session_db()

        if args.data:
            import_csv(conn, spec.mappings, Path(args.data))

        plans = plan(spec, session, conn)
        close_session_db(conn)

        total_frames = 0
        total_videos = 0
        for p in plans:
            total_videos += 1
            total_frames += len(p.frames)
            print(f"{p.video_file.path.name}: {len(p.frames)} frames")
            for f in p.frames:
                utc_time = p.video_file.utc_start + timedelta(seconds=f.offset_s)
                sensor_str = ""
                if f.sensor_snapshot:
                    sensor_str = "  sensor=" + " ".join(
                        f"{k}={v}" for k, v in f.sensor_snapshot.items()
                    )
                print(f"  {utc_time.isoformat()}  offset={f.offset_s:.3f}s{sensor_str}")

        print(f"\nTotal: {total_frames} frames across {total_videos} video(s)")
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def main() -> None:
    """Build the argument parser and run the extraction or planning pipeline.

    CLI Arguments:
        source      one or more video file paths, or a single directory path
        --spec      path to YAML extraction spec (required)
        --plan      dry-run: plan extraction without decoding frames
        --output    directory to write extracted frames (default: ./frames)
        --data      path to sensor CSV file (optional)
    """
    parser = argparse.ArgumentParser(
        prog="deep-framex",
        description="Extract annotated frames from deep sea video.",
    )
    parser.add_argument(
        "source",
        nargs="+",
        help=(
            "Directory of video files, or one or more explicit video file paths. "
            "For a single file, wrap it in a list: deep-framex /path/to/file.mp4 --spec ..."
        ),
    )
    parser.add_argument(
        "--spec",
        required=True,
        metavar="YAML",
        help="Path to the extraction spec YAML file.",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Dry-run: plan extraction without decoding or writing any frames.",
    )
    parser.add_argument(
        "--data",
        metavar="CSV",
        default=None,
        help="Path to sensor CSV file (optional).",
    )
    parser.add_argument(
        "--output",
        metavar="DIR",
        default="./frames",
        help="Directory to write extracted frames (default: ./frames).",
    )
    args = parser.parse_args()
    sys.exit(cmd_plan(args) if args.plan else cmd_extract(args))
