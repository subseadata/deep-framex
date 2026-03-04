# soi-frame-extractor

Frame extraction library for deep sea video.  Frames are self-describing — metadata is embedded directly into image files so context travels with the frame into any downstream system.

## Installation and Use

```
pip install soi-frame-extractor
```

Run from the command line:

```
soi-extract <source> --spec <yaml> [--data <csv>] [--output <dir>]
```

- `source`    path to a directory of video files, or one or more explicit video file paths
- `--spec`    path to a YAML extraction spec (required)
- `--data`    path to a sensor CSV file (optional — enables depth/location constraints and metadata)
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

mappings:                    # omit entirely if no sensor CSV is provided
  timestamp: utc_time        # required if mappings is present
  latitude:  lat             # optional — enables GPS metadata in output frames
  longitude: lon             # optional — accepts -180/+180 or 0-360
  depth:     z               # optional
  temp:      temperature_c   # any additional columns are accepted

metadata:                    # optional — arbitrary key/value pairs
  cruise_id: FK250101        # written to XMP and iFDO in all output frames
  dive_id:   S0042
  vehicle:   SuBastian

filename_template: "{dive_id}_{depth}m_T{utc}.jpg"  # optional
# available variables: {utc}, {video_stem}, {offset_s}, any mappings key, any metadata key
# omit to use the default: {utc}_{video_stem}.jpg

xmp_namespace_uri:    https://soi-frame-extractor.org/xmp/v1/  # optional
xmp_namespace_prefix: sfe                                       # optional
```

All timestamps must be ISO 8601 with an explicit UTC offset (`Z` or `+00:00`).

**Rule composition:** periods and constraints on the *same* rule intersect — frames are only extracted where all conditions are simultaneously met.  Separate rules are unioned — each rule contributes its timestamps independently and the planner deduplicates before extraction.

## Structure

```
src/soi_frame_extractor/
├── models/          # pydantic data models and metadata field registry
├── config/          # YAML spec parsing and video file discovery
├── data/            # CSV import
├── db/              # session SQLite (in-memory) — sensor readings and frame plan
├── planning/        # translate intervals, periods, sensor constraints into extraction offsets
├── extraction/      # open video containers and decode frames
├── metadata/        # embed metadata into image files (EXIF, IPTC, XMP, iFDO)
├── output/          # write frames to disk
├── utils/           # shared helpers (coordinate conversion, etc.)
├── cache/           # (planned) cache sampling and indexing
```

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

## Function Map

### data importer
- loads a CSV file from a local path
- validates column names as legal identifiers; rejects non-float data columns
- writes all rows into the session database `sensor_readings` table under a dynamically-built schema matching the CSV headers
- timestamp column is required and named explicitly by the user in the YAML `mappings:` block
- no assumptions about which sensor columns are present — one or thirty are equally valid
- returns an `ImportedDataset` describing available columns and time range

### session database
- holds two tables for the duration of one extraction run, then is discarded
- `sensor_readings` — all CSV rows indexed by timestamp (Unix epoch float); schema built dynamically from CSV headers at import time
- `frame_plan` — one row per frame to extract; carries status (`planned → extracted → written`) and a `sensor_snapshot` JSON blob of interpolated sensor values at that timestamp
- downstream stages (metadata writer, frame writer) read from `frame_plan` only — they never re-query `sensor_readings`

### timestamp correlator
- aligns separate time references into one: sensor/data UTC, video UTC, video time *(t=0 at start->end)*
- everything downstream depends on this being right [how do we handle bad sync events? manual override?]
- alignment point:
    - assume video is authoritative? 

### user ingress
- accepts a YAML config file defining rules, optional sensor mappings, and optional project metadata
- accepts video source as either a directory or an explicit list of file paths
- accepts an optional sensor CSV; if provided, loads it into the session database via the data importer
- validates all datetimes as ISO 8601 UTC; rejects naive timestamps
- resolves video paths and probes each file for metadata (utc_start from embedded `creation_time` tag, duration)
- validates the filename template against available keys at startup — fails fast before any extraction begins
- produces an ExtractionSpec and VideoSession ready for the planner

### extraction planner
- processes each rule independently against the session database
- per rule: starts with the full session, intersects UTC periods if present, intersects sensor constraint windows if present, then samples at interval_s
- sensor constraint windows are resolved by querying `sensor_readings` for time ranges where conditions are met
- interpolates sensor values at each planned timestamp and writes them as a JSON snapshot into `frame_plan`
- across rules: timestamps are unioned and deduplicated before extraction
- the extractor never sees rules, only timestamps

### extractor
- reads frames at the timestamps the planner provides
- opens each video container once, seeks offsets in ascending order, then closes it before moving to the next video
- reads the `sensor_snapshot` and `project_metadata` for each frame from `frame_plan` and assembles a complete `ExtractedFrame`
- single responsibility: get the pixel data at offset T and attach its pre-computed metadata

### cache sampler
- used when the extraction planner finds a cache hit
- subsamples pre-cached high-frequency frameset for coarser intervals *(e.g., a request for 1 every 10 seconds just filters a cached 1fps set)*

### cache indexer
- checks whether a video already has pre-computed frames at a given rate
- reads a cache manifest from storage
- returns which requested timestamps are available and which need extraction

### metadata writer
- embeds a frame's metadata record into the image file
- four layers:
  - EXIF GPS tags *(lat, lon, depth, timestamp)*
  - IPTC fields *(title, keywords, standardized caption w/ credit)*
  - XMP fields *(canonical sensor fields and project metadata under a user-configurable namespace; defaults to `sfe:` / `https://soi-frame-extractor.org/xmp/v1/`)*
  - iFDO fields *(scientific image metadata standard)*
- canonical fields (latitude, longitude, depth) are routed to their prescribed layer and tag via the internal field registry
- all other sensor columns and project metadata flow to XMP automatically

### frame writer
- writes a frame image to storage (local or cloud)
- sets output format *(JPEG or TIFF)*
- filename generated from a user-supplied template string using canonical sensor and metadata keys *(e.g., `{dive_id}_{depth}m_T{utc}.jpg`)*; falls back to `{utc}_{video_stem}.jpg` per-frame if a sensor value is absent
- returns `(path, ExtractedFrame)` pairs so the metadata writer can annotate each file immediately after

### cache writer
- records a completed extraction in a cache manifest
- stores what rate was extracted, how many frames, time range, storage prefix
- enables the frame cache index to answer future requests without scanning storage

### frame scorer
- analyzes frames and produces quality/analysis scores *(e.g., sharpness, blue water, pure black, others...?)*
- attaches scores to the frame record
- never discards frames — flags them and lets the user decide what to do

### data evaluator
- plots sensor data *(time-series of depth, temperature, etc.)* so you can see what happened during a dive
- interactive — select time ranges and value bounds graphically *(nice-to-have feature depending on the interface)*
- outputs selections as time windows and environmental conditions ready to feed into the extraction planner

### frame annotator
- burns data overlay onto a frame image *(depth, temp, timestamp, dive ID)*
- returns a new frame — does not modify the original

### map viewer
- plots frame positions on an interactive map using embedded geospatial metadata
- useful for reviewing spatial coverage before or after extraction
