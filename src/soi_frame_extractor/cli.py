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
    pass


def main() -> None:
    """Build the argument parser and run the extraction pipeline.

    Since this is a CLI, it doesn't take classic Args: and give Returns:,
    it just calls cmd_extract above with the parsed arguments from the 
    command line.

    CLI Arguments:
        source      one or more video paths or a directory
        --spec      path to YAML extraction spec (required)
        --output    directory to write extracted frames (defaults to ./frames)
        --data      path to sensor CSV file (optional)

    """
    # TODO: if probe or plan/dry run modes are added later, migrate to a subparser
    pass
