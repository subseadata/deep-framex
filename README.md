# soi-frame-extractor

Frame extraction library for deep sea video.  Frames are self-describing — metadata is embedded directly into image files so context travels with the frame into any downstream system.

## Installation

Install from source:

**uv:**
```
uv pip install git+https://github.com/schmidtocean/soi-frame-extractor
```

**Pip:**
```
git clone <repo>
cd soiFrameExtractor
pip install -e .
```

## Command-line use

```
soi-extract <source> --spec <yaml> [--data <csv>] [--output <dir>]
```

- `source`    path to a directory of video files, or one or more explicit video file paths
- `--spec`    path to a YAML extraction spec (required)
- `--data`    path to a sensor CSV file (optional — enables depth/location constraints and sensor metadata)
- `--output`  directory to write extracted frames (default: `./frames`)

### Extraction spec

The spec defines one or more extraction rules plus optional sensor column mappings and project metadata.  Each rule requires an interval and optionally UTC time periods, sensor constraints, or both.  If no periods or constraints are given, the rule applies to the full session.

```yaml
rules:
  # 1 frame every 10 seconds for the entire session
  - interval_s: 10.0

  # 1 frame every 2 seconds during a specific UTC window
  - interval_s: 2.0
    periods:
      - start: "2025-11-15T10:25:00Z"
        end:   "2025-11-15T10:30:00Z"

  # 1 frame every 5 seconds while depth is between 1000 and 1200 m
  - interval_s: 5.0
    constraints:
      - column: depth
        min: 1000
        max: 1200

  # periods and constraints on the same rule intersect:
  # 1 frame every 2 seconds during the UTC window AND while below 500 m
  - interval_s: 2.0
    periods:
      - start: "2025-11-15T10:25:00Z"
        end:   "2025-11-15T10:30:00Z"
    constraints:
      - column: depth
        max: 500

mappings:                       # omit entirely if no sensor CSV is provided
  timestamp:   Timestamp        # required — your CSV column that holds UTC time
  latitude:    Latitude_ddeg    # your CSV column for latitude
  longitude:   Longitude_ddeg   # your CSV column for longitude
  depth:       Depth_m          # your CSV column for depth
  temperature: Temp_degC        # any other columns you want to use

metadata:                    # optional — arbitrary key/value pairs
  cruise_id: FK250101        # written to iFDO and XMP in all output frames
  dive_id:   S0042
  vehicle:   SuBastian

filename_template: "{dive_id}_{depth}m_T{utc}.jpg"  # optional
# available variables: {utc}, {video_stem}, {offset_s}, any mappings key, any metadata key
# omit to use the default: {utc}_{video_stem}.jpg

stream_output: false  # true writes each frame to disk immediately (lower memory use)
max_workers: 1        # number of parallel worker processes; see below
```

All timestamps must be ISO 8601 with an explicit UTC offset (`Z` or `+00:00`).

### Mapping your sensor data

The `mappings` block tells the tool which columns to read from your CSV and what to call them.  Each line follows this pattern:

```
name_for_this_tool: Column Name In Your CSV
```

**The right side** is your CSV column header, copied exactly as it appears — including any spaces or special characters.  If your column is named `VelocityFwd_m/s`, write that on the right.

**The left side** is the name the tool will use for that column — in constraint rules, filename templates, and image metadata.  It must contain only letters, numbers, and underscores.  If your CSV has `VelocityFwd_m/s`, write something like `velocityfwd` on the left.

**Only the columns you list are loaded.**  Everything else in your CSV is ignored — columns with string values, status flags, or other non-numeric content are fine as long as you do not map them.  Any column you *do* map must contain numeric values.

The names on the left side determine where values end up in output metadata.  These specific names trigger automatic routing to EXIF GPS tags and the iFDO manifest:

| Left-side name | Where it goes |
|---|---|
| `latitude` | EXIF GPSLatitude + iFDO image-latitude — decimal degrees only (e.g. `-44.2895`), negative = south |
| `longitude` | EXIF GPSLongitude + iFDO image-longitude — decimal degrees only (e.g. `-59.9191`), negative = west; 0–360 also accepted |
| `depth` | EXIF GPSAltitude (tagged as below sea level) + iFDO image-depth |
| `altitude` | iFDO image-altitude-meters |
| `heading` | iFDO image-heading |
| `pitch` | iFDO image-pitch |
| `roll` | iFDO image-roll |

Any other name you choose is fine — the values are written to the XMP layer of each image.  For example, mapping `z: Depth_m` stores depth in XMP only.  Mapping `depth: Depth_m` puts it in EXIF, XMP, and iFDO.

The `timestamp` entry is required if you provide a CSV.

**Rule composition:** periods and constraints on the *same* rule intersect — frames are only extracted where all conditions are simultaneously met.  Separate rules are unioned — each rule contributes its timestamps independently and duplicates are removed.

## Parallel and distributed extraction

By default the tool extracts one video at a time.  Setting `max_workers` runs a pool of worker processes — if you have 27 videos and 5 workers, all 5 stay busy until all 27 are done.

```yaml
max_workers: 4       # up to 4 videos extracted at once
stream_output: true  # strongly recommended with max_workers > 1
```

**Always set `stream_output: true` when using multiple workers.**  Without it each worker buffers an entire video's decoded frames in memory before writing.  At 4K with a 10-second interval that is roughly 1.4 GB per worker.  With `stream_output: true` peak memory stays at one frame (~24 MB) per worker regardless of video length.

**Include `{utc}` in your filename template when using multiple workers.**  Workers write to the same output directory concurrently.  The planner guarantees unique timestamps, so `{utc}` guarantees unique filenames with no collision risk.

`max_workers` uses Python's `ProcessPoolExecutor` — local subprocesses on the same machine.  Each worker receives a self-contained extraction plan and opens its own copy of the video file.  No shared state between workers.

### Distributed / cloud workers

For Kubernetes, Airflow, AWS Batch, or any task queue, call the pipeline stages directly.  Planning runs once on a coordinator; each worker only needs its own video file.

```python
from soi_frame_extractor.config.spec_parser import spec_from_file
from soi_frame_extractor.config.video_discovery import discover_videos
from soi_frame_extractor.extraction.video_session import create_video_session
from soi_frame_extractor.db.session_db import create_session_db, close_session_db
from soi_frame_extractor.data.importer import import_csv
from soi_frame_extractor.planning.planner import plan
from soi_frame_extractor.pipeline import _extract_and_write_video
from soi_frame_extractor.metadata.ifdo import write_ifdo_manifest

# --- planning (runs once, on the coordinator) ---
spec    = spec_from_file(spec_path)
session = create_video_session(discover_videos(video_source))
conn    = create_session_db()
if csv_path:
    import_csv(csv_path, conn, spec.mappings)
plans = plan(spec, session, conn)
close_session_db(conn)   # database only needed for planning; discard it here

# --- dispatch (one plan = one worker) ---
for p in plans:
    payload = p.model_dump_json()   # self-contained JSON, ~2 KB per video
    my_queue.send(payload)          # Airflow task, K8s Job, SQS message, etc.

# --- each worker ---
# plan = VideoExtractionPlan.model_validate_json(payload)
# result = _extract_and_write_video(plan, output_dir, ...)
# return result   # list of (path, FrameMetadata)

# --- gather and write manifest (back on coordinator) ---
all_results = my_queue.collect_all()
write_ifdo_manifest([item for r in all_results for item in r], output_dir)
```

Each worker only needs access to its own video file — not the sensor CSV, the session database, or any other video.  For cloud-hosted video (S3, GCS), the file must currently be downloaded before the worker runs; direct remote URL support is planned.

## Using as a library

Each pipeline stage is a standalone function.  You can call any stage independently without going through the CLI or the full pipeline.

```python
from soi_frame_extractor.config.spec_parser import spec_from_file
from soi_frame_extractor.config.video_discovery import discover_videos
from soi_frame_extractor.extraction.video_session import create_video_session
from soi_frame_extractor.extraction.frame_extractor import decode_frames
from soi_frame_extractor.planning.planner import plan
from soi_frame_extractor.db.session_db import create_session_db, close_session_db
from soi_frame_extractor.data.importer import import_csv
from soi_frame_extractor.output.output_frames import write_frame
from soi_frame_extractor.metadata.ifdo import write_ifdo_manifest
```

**Planning only** — inspect what would be extracted before committing to a run:

```python
spec    = spec_from_file("my_spec.yaml")
session = create_video_session(discover_videos(Path("video_dir/")))
conn    = create_session_db()
plans   = plan(spec, session, conn)
close_session_db(conn)

for p in plans:
    print(p.video_file.path.name, len(p.frames), "frames")
```

**Extraction without writing** — get raw frames as NumPy arrays:

```python
for frame in decode_frames(video_plan):
    # frame.frame is (H, W, 3) uint8 RGB
    # frame.metadata holds utc_timestamp, sensor values, project metadata
    process(frame.frame)
```

**Writing without the full pipeline** — embed metadata and save an already-decoded frame:

```python
from soi_frame_extractor.output.output_frames import write_frame

path, meta = write_frame(frame, output_dir, filename_template=None,
                         xmp_namespace_uri="https://example.org/",
                         xmp_namespace_prefix="myns")
```

## Generating BIIGLE metadata from existing images

If you already have a set of extracted images and just need a BIIGLE-compatible metadata CSV — without re-extracting from video — use the standalone assembler.  No video files or pixel data are required.

You need a list of `(filename, utc_datetime)` pairs.  There are two helpers depending on how your filenames are structured:

**Filenames produced by this tool** — parse the timestamp directly out of the filename using the same template string:

```python
from pathlib import Path
from soi_frame_extractor.utils.timestamps import parse_filename_template

files = [
    (p.name, parse_filename_template(p, "{dive_id}_{utc}"))
    for p in sorted(Path("frames/").glob("*.jpg"))
]
```

**Generic filenames with a separate CSV** — read a CSV that maps filenames to timestamps:

```python
from soi_frame_extractor.utils.timestamps import parse_file_list_csv

# file_list.csv columns: filename, timestamp
files = parse_file_list_csv(Path("file_list.csv"))
```

Then assemble and write:

```python
from soi_frame_extractor.metadata.assemble import assemble_biigle_records
from soi_frame_extractor.metadata.biigle import write_biigle_manifest
from soi_frame_extractor.models.models import ColumnMappings

records = assemble_biigle_records(
    files=files,
    csv_path=Path("sensors.csv"),       # omit if no sensor data
    mappings=ColumnMappings(
        timestamp="Timestamp",
        latitude="Lat_ddeg",
        longitude="Lon_ddeg",
        depth="Depth_m",
    ),
    project_metadata={"cruise_id": "FK250101", "dive_id": "S0042"},
)

write_biigle_manifest(records, Path("output/"))
```

`assemble_biigle_records` interpolates sensor values at each image's timestamp using the same median-based interpolation as the extraction pipeline.  The sensor CSV need not align exactly with frame timestamps.

## Structure

```
src/soi_frame_extractor/
├── models/          # data models and metadata field routing registry
├── config/          # YAML spec parsing and video file discovery
├── data/            # CSV import
├── db/              # in-memory SQLite session database — used during planning only
├── planning/        # translate rules, time periods, and sensor constraints into frame offsets
├── extraction/      # open video containers and decode frames
├── metadata/        # embed metadata into image files (EXIF, IPTC, XMP) and write iFDO sidecar
├── output/          # write frames to disk
├── utils/           # coordinate conversion
├── cache/           # (planned) cache sampling and indexing
└── viz/             # (planned) map view of extracted frame positions
```

## Pipeline stages

### Spec parser (`config/spec_parser.py`)
Reads a YAML spec file into an `ExtractionSpec`.  Validates all rules, periods, constraints, and datetime strings.  Raises `ValueError` immediately on any invalid input.

### Video discovery (`config/video_discovery.py`)
Resolves a directory or an explicit list of file paths into probed `VideoFile` objects.  Each `VideoFile` carries its UTC start time (read from the file's `creation_time` tag) and duration.

### Session database (`db/session_db.py`)
An in-memory SQLite database used only during planning.  Holds sensor readings from the CSV and the resulting frame plan.  Discarded after `plan()` returns — the extractor does not use it.

### Data importer (`data/importer.py`)
Loads a CSV into the session database.  Only the columns listed in the `mappings` block are imported; everything else is ignored.  Left-side names become the column names used everywhere downstream.

### Planner (`planning/planner.py`)
Processes each rule against the session database — intersecting time periods and sensor constraint windows, sampling at `interval_s`, then unioning and deduplicating across all rules.  Interpolates sensor values at each planned timestamp and packages everything into self-contained `VideoExtractionPlan` objects.  After this stage the database is no longer needed.

### Extractor (`extraction/frame_extractor.py`)
A generator that yields `ExtractedFrame` objects from a single `VideoExtractionPlan`.  Opens the video file, seeks to each planned offset in order, decodes the closest frame, and attaches the pre-computed sensor values and project metadata.  No database access.  Each plan is a self-contained unit of work — suitable for running in a subprocess or on a remote worker.

### Metadata writer (`metadata/apply_metadata.py`)
Builds EXIF, IPTC, and XMP byte blocks for a single frame.  Called by the frame writer at save time — metadata is embedded in a single Pillow save, not written in a separate pass.

- **EXIF**: GPS latitude, longitude, altitude (depth), timestamp, camera make/model
- **IPTC**: credit, source, copyright notice, caption, date/time created
- **XMP**: creation date, plus all sensor columns and project metadata not already routed to EXIF or IPTC — written under a configurable namespace (default: `sfe:` / `https://soi-frame-extractor.org/xmp/v1/`)

### iFDO manifest (`metadata/ifdo.py`)
Writes a single `ifdo.json` sidecar file for the whole extraction run.  One entry per frame, keyed by filename, containing UUID, datetime, position, depth, orientation, and project fields.  Written once at the end of a run after all frames are complete.  Separate from the per-image metadata — does not require re-reading any image files.

### Frame writer (`output/output_frames.py`)
Writes frames to a local output directory.  Generates filenames from the user-supplied template, calls the metadata builders, and saves each image once.  Returns `(path, FrameMetadata)` pairs — pixel data is written and discarded; the returned metadata is sufficient to build the iFDO manifest without holding frames in memory.

Supports JPEG (full metadata: EXIF + IPTC + XMP) and TIFF (EXIF only).

## User Story Functionality (I want to...)
- extract frames from video at a defined time interval *(e.g., 1 every 5 seconds, 1 every 10 seconds)*
- extract frames from video during specific time periods *(e.g., from 00:30:00-03:20:00 video time or 22:30:00-22:45:00 UTC)*
- extract frames from video during specific environmental conditions *(e.g., get frames only for depths from 1000-1200m, only from temperatures 2-3C)*
- extract frames under a mix of the above conditions *(e.g., 1 every 5 seconds while <1000m, 1 every 10 seconds while <500m, 1 every second from 12:00:00-13:00:00 UTC)*
- extract frames from locally-hosted video
- extract frames from cloud-hosted video files (avoid downloading them — stream only what's needed)
- extract frames from mov files or mp4 files
- extract frames and name them per an arbitrary file naming scheme *(e.g., frame1, frame2; FKt999901_S9999_T23:30:01, FKt999901_S9999_1200m_T11:35:24)*
- import data *(csv with timestamp, plus alignment of timestamps)*
- view and evaluate data *(plot variables for selecting data bounds for extraction)*
- attach metadata to extracted frames *(embedded in the image file — EXIF, IPTC)*
- attach geospatial data to extracted frames *(interpolated from log, embedded as standard GPS EXIF tags)*
- overlay data onto extracted frames visually
- view a map of extracted frames
- score/flag frames for analysis or quality *(flag blue water, completely black frames, other analyses - focus?)*
- [We want to] serve pre-computed standard framesets and subsample them rather than re-extracting from video *(1fps base rate, subsample for coarser intervals)*
