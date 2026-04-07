"""Pipeline orchestrator

Top-level function that wires all pipeline stages together and drives an
extraction run from a YAML spec to annotated image files on disk.

Stage order:
    1. Parse spec from YAML
    2. Discover and probe video files
    3. Assemble VideoSession (sorted by utc_start)
    4. Initialise session database (in-memory SQLite)
    5. Import sensor CSV into session database (if provided)
    6. Validate filename template against known keys (if template supplied)
    7. Plan frame offsets — produces self-contained VideoExtractionPlan objects
    8. Close session database — no longer needed after planning
    9. Extract frames and write to disk (sequential or parallel)
   10. Write iFDO JSON sidecar manifest for the full image set

Extraction modes (controlled by spec.max_workers and spec.stream_output):

    max_workers=1 (default): sequential extraction, one video at a time.

    max_workers>1: one worker process per video, up to max_workers running
        concurrently.  Each worker receives a self-contained VideoExtractionPlan
        and opens its video file independently — no shared state between workers.
        Strongly recommended: set stream_output: true when using multiple workers
        to avoid multiplying peak memory by the number of concurrent workers.

    stream_output=False (default): each worker buffers a full video's frames
        before writing.  Peak memory ≈ frames_per_video × 24 MB per worker.
    stream_output=True: each worker writes frames one at a time as decoded.
        Peak memory ≈ 24 MB per worker regardless of video length or interval.

NOTE for cloud / distributed use: _extract_and_write_video is a plain function
that takes a serialisable VideoExtractionPlan.  For Kubernetes, Airflow, or
any task queue, replace the ProcessPoolExecutor block with your dispatcher:
serialise each plan to JSON (plan.model_dump_json()), send to a worker, collect
list[tuple[Path, FrameMetadata]] results, then call write_ifdo_manifest.
Each worker only needs access to its own video file — see frame_extractor.py
for notes on remote (S3/GCS) video support.
"""

import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from ..config.spec_parser import spec_from_file
from ..config.video_discovery import discover_videos
from ..data.importer import import_csv
from ..db.session_db import create_session_db, close_session_db
from ..extraction.frame_extractor import extract_frames
from ..extraction.video_session import create_video_session
from ..metadata.biigle import write_biigle_manifest
from ..metadata.ifdo import write_ifdo_manifest
from ..models.models import FrameMetadata, VideoExtractionPlan
from ..output.output_frames import output_frames, validate_filename_template, write_frame
from ..planning.planner import plan as plan_extraction


def _extract_and_write_video(
    video_plan: VideoExtractionPlan,
    output_dir: Path,
    filename_template: str | None,
    xmp_namespace_uri: str,
    xmp_namespace_prefix: str,
    stream_output: bool,
) -> list[tuple[Path, FrameMetadata]]:
    """Extract and write all frames for one video file.

    This is the unit of work for both sequential and parallel execution.
    It must be a module-level function (not a lambda or nested function) so
    that ProcessPoolExecutor can pickle it for worker processes.

    For distributed use (Kubernetes, Airflow, etc.) this function contains
    everything a worker needs: receive a VideoExtractionPlan, call this,
    return the result list to the coordinator.

    Args:
        video_plan:           self-contained plan for one video.
        output_dir:           directory to write image files into.
        filename_template:    filename format string, or None for default.
        xmp_namespace_uri:    URI for the custom XMP namespace.
        xmp_namespace_prefix: prefix for the custom XMP namespace.
        stream_output:        if True, write each frame immediately to keep
                              memory use to one frame at a time.

    Returns:
        List of (Path, FrameMetadata) pairs for every frame written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if stream_output:
        # Write each frame immediately — peak memory is one decoded frame.
        written = []
        for frame in extract_frames(video_plan):
            result = write_frame(
                frame, output_dir, filename_template,
                xmp_namespace_uri, xmp_namespace_prefix,
            )
            written.append(result)
        return written
    else:
        # Buffer all frames for this video, then write as a batch.
        frames = list(extract_frames(video_plan))
        return output_frames(
            frames, output_dir, filename_template,
            xmp_namespace_uri, xmp_namespace_prefix,
        )


def run(
    spec_path: Path,
    video_source: Path | list[Path],
    output_dir: Path,
    csv_path: Path | None = None,
) -> None:
    """Execute a full extraction run from spec to annotated image files on disk.

    Reads max_workers and stream_output from the spec (set in YAML).
    max_workers=1 (default) runs sequentially.  max_workers>1 launches one
    worker process per video up to that limit.

    Args:
        spec_path:    path to the YAML extraction spec.
        video_source: directory of video files, or an explicit list of paths.
        output_dir:   directory to write output image files into.
        csv_path:     path to sensor CSV, or None if no sensor data.

    Raises:
        FileNotFoundError: if spec_path, any video file, or csv_path does not
                           exist.
        ValueError:        if the spec is invalid, the filename template
                           references an unknown key, or any planned timestamp
                           falls outside the video session span.
        OSError:           if output_dir cannot be created or a file cannot be
                           written.
    """
    # --- Stage 1: parse spec ---
    spec = spec_from_file(spec_path)

    # --- Stage 2 & 3: discover videos and assemble session ---
    video_files = discover_videos(video_source)
    session = create_video_session(video_files)

    # --- Stage 4: init session database (used only during planning) ---
    conn = create_session_db()

    try:
        # --- Stage 5: import sensor CSV ---
        sensor_keys: list[str] = []
        if csv_path is not None and spec.mappings is None:
            raise ValueError(
                "A CSV file was provided (--data) but the spec has no 'mappings' block. "
                "Add mappings (including 'timestamp') or omit --data."
            )
        if csv_path is not None and spec.mappings is not None:
            dataset = import_csv(csv_path, conn, spec.mappings)
            sensor_keys = dataset.columns

        # --- Stage 6: validate filename template ---
        if spec.filename_template is not None:
            validate_filename_template(
                spec.filename_template,
                sensor_keys,
                list(spec.project_metadata.keys()),
            )

        # --- Stage 7: plan ---
        # plan() produces self-contained VideoExtractionPlan objects — sensor
        # snapshots and project metadata are embedded in each plan, so nothing
        # downstream needs the database.
        plans = plan_extraction(spec, session, conn)

    finally:
        # --- Stage 8: close DB — done with it ---
        # The session database is internal scaffolding for the planning stage.
        # Everything the extractor needs is now in the plan objects.
        close_session_db(conn)

    # --- Stage 9: extract and write ---
    output_dir.mkdir(parents=True, exist_ok=True)

    # Cap workers to the number of videos — no benefit spawning more.
    effective_workers = min(spec.max_workers, len(plans))

    if effective_workers > 1 and not spec.stream_output:
        print(
            f"Warning: stream_output=false with {effective_workers} parallel workers "
            f"multiplies peak memory by {effective_workers}. "
            "Consider setting stream_output: true in your spec.",
            file=sys.stderr,
        )

    worker_args = (
        output_dir,
        spec.filename_template,
        spec.xmp_namespace_uri,
        spec.xmp_namespace_prefix,
        spec.stream_output,
    )

    all_written: list[tuple[Path, FrameMetadata]] = []

    if effective_workers <= 1:
        # Sequential: process videos one at a time in session order.
        for video_plan in plans:
            all_written.extend(_extract_and_write_video(video_plan, *worker_args))
    else:
        # Parallel: one worker process per video, up to effective_workers at once.
        # Each worker is independent — no shared state, no shared database.
        # NOTE: for Kubernetes / Airflow / cloud workers, replace this block with
        # your task dispatcher.  Serialise each plan with plan.model_dump_json(),
        # send to workers, collect list[tuple[Path, FrameMetadata]] results here.
        with ProcessPoolExecutor(max_workers=effective_workers) as executor:
            futures = {
                executor.submit(_extract_and_write_video, video_plan, *worker_args): video_plan
                for video_plan in plans
            }
            for future in as_completed(futures):
                all_written.extend(future.result())

        # Sort by timestamp — parallel workers finish in arbitrary order, but
        # the iFDO manifest should be in chronological order.
        all_written.sort(key=lambda pair: pair[1].utc_timestamp)

    # --- Stage 10: write iFDO and BIIGLE manifests ---
    write_ifdo_manifest(all_written, output_dir)
    write_biigle_manifest(all_written, output_dir)
