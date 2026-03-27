"""Command-line interface for soi-frame-extractor

Entry point: __main__.py calls main(), which builds the argument parser
and runs the extraction pipeline.

Usage:
    soi-extract <source> --spec <yaml> [--output <dir>]

    <source>  — path to a directory of video files, or one or more explicit
                video file paths.  Passed directly to discover_videos, so the
                same rules apply: directory OR list; single bare file raises
                ValueError (wrap it: soi-extract /path/to/file.mp4).
"""

import argparse
import sys
from pathlib import Path

from .pipeline import run


def cmd_extract(args: argparse.Namespace) -> int:
    """Run the full extraction pipeline from parsed CLI arguments.

    Delegates entirely to pipeline.run().  Catches known error types,
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
        run(
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


def main() -> None:
    """Build the argument parser and run the extraction pipeline.

    CLI Arguments:
        source      one or more video file paths, or a single directory path
        --spec      path to YAML extraction spec (required)
        --output    directory to write extracted frames (default: ./frames)
        --data      path to sensor CSV file (optional)
    """
    # TODO: if probe or dry-run modes are added later, migrate to subparsers
    parser = argparse.ArgumentParser(
        prog="soi-extract",
        description="Extract annotated frames from deep sea video.",
    )
    parser.add_argument(
        "source",
        nargs="+",
        help=(
            "Directory of video files, or one or more explicit video file paths. "
            "For a single file, wrap it in a list: soi-extract /path/to/file.mp4 --spec ..."
        ),
    )
    parser.add_argument(
        "--spec",
        required=True,
        metavar="YAML",
        help="Path to the extraction spec YAML file.",
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
    sys.exit(cmd_extract(args))
