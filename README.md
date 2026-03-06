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

mappings:                       # omit entirely if no sensor CSV is provided
  timestamp:   Timestamp        # required — your CSV column that holds UTC time
  latitude:    Latitude_ddeg    # your CSV column for latitude
  longitude:   Longitude_ddeg   # your CSV column for longitude
  depth:       Depth_m          # your CSV column for depth
  temperature: Temp_degC        # any other columns you want to use

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

### Mapping your sensor data

The `mappings` block tells the tool which columns to read from your CSV and what to call them.  Each line follows this pattern:

```
name_for_this_tool: Column Name In Your CSV
```

**The right side** is your CSV column header, copied exactly as it appears — including any spaces or special characters.  If your spreadsheet column title says `VelocityFwd_m/s`, write `VelocityFwd_m/s` on the right.

**The left side** is the name the tool will use for that column — in constraint rules, filename templates, and image metadata.  It must contain only letters, numbers, and underscores (no spaces, slashes, or special characters).  If your CSV has `VelocityFwd_m/s` and you want to use it, write something like `velocityfwd` on the left.

**Only the columns you list are loaded.**  Everything else in your CSV is ignored — columns with string labels, status flags, or other non-numeric content are fine as long as you do not map them.  Any column you *do* map must contain numeric values; the import will fail with an error if it finds something it cannot convert to a number.

The names on the left side matter for metadata output.  The tool recognises these specific names and writes them to the correct fields in image EXIF tags and the iFDO manifest automatically:

| Left-side name | Where it goes |
|---|---|
| `latitude` | EXIF GPSLatitude + iFDO image-latitude — **decimal degrees only** (e.g. `-44.2895`), negative = south. Degrees-minutes-seconds and degrees-decimal-minutes are not supported — convert to decimal degrees first. |
| `longitude` | EXIF GPSLongitude + iFDO image-longitude — **decimal degrees only** (e.g. `-59.9191`), negative = west; 0–360 also accepted. Degrees-minutes-seconds and degrees-decimal-minutes are not supported — convert to decimal degrees first. |
| `depth` | EXIF GPSAltitude (below sea level) + iFDO image-depth |
| `altitude` | iFDO image-altitude-meters |
| `heading` | iFDO image-heading |
| `pitch` | iFDO image-pitch |
| `roll` | iFDO image-roll |

Any other name you choose is fine — the values will be saved and written to the XMP layer of each image, just not to EXIF or iFDO.  For example, mapping `z: Depth_m` will store the depth values and write them to XMP, but they will not appear in EXIF GPS fields.  Mapping `depth: Depth_m` puts them everywhere.

The `timestamp` entry is required if you provide a CSV.  It tells the tool which column holds the UTC time for each sensor reading.

**Rule composition:** periods and constraints on the *same* rule intersect — frames are only extracted where all conditions are simultaneously met.  Separate rules are unioned — each rule contributes its timestamps independently and the planner deduplicates before extraction.

## Structure

```
src/soi_frame_extractor/
├── models/          # pydantic data models and metadata field registry
├── config/          # YAML spec parsing and video file discovery
├── data/            # CSV import; (planned) sensor data visualisation and range selection
├── db/              # session SQLite (in-memory) — sensor readings and frame plan
├── planning/        # translate intervals, periods, sensor constraints into extraction offsets
├── extraction/      # open video containers and decode frames
├── metadata/        # embed metadata into image files (EXIF, IPTC, XMP, iFDO)
├── output/          # write frames to disk
├── utils/           # shared helpers (coordinate conversion, etc.)
├── cache/           # (planned) cache sampling and indexing
└── viz/             # (planned) map view of extracted frame positions
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
- reads only the columns listed in the `mappings:` block — every other column in the CSV is ignored
- left-side mapping names become the column names in the database; right-side CSV column names are only used at import time
- validates that left-side names are legal identifiers (letters, digits, underscores); right-side CSV names can contain anything
- all sensor values must be numeric (castable to float); timestamp must be ISO 8601 UTC
- returns an `ImportedDataset` describing which columns were loaded and the time range of the data

### session database
- holds two tables for the duration of one extraction run, then is discarded
- `sensor_readings` — all CSV rows indexed by timestamp (Unix epoch float); schema built dynamically from CSV headers at import time
- `frame_plan` — one row per frame to extract; carries status (`planned → extracted → written`) and a `sensor_snapshot` JSON blob of interpolated sensor values at that timestamp
- downstream stages (metadata writer, frame writer) read from `frame_plan` only — they never re-query `sensor_readings`

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
- writes frame images to a local output directory
- sets output format *(JPEG or TIFF)*
- filename generated from a user-supplied template string using canonical sensor and metadata keys *(e.g., `{dive_id}_{depth}m_T{utc}.jpg`)*; falls back to `{utc}_{video_stem}.jpg` per-frame if a sensor value is absent
- returns `(path, ExtractedFrame)` pairs so the metadata writer can annotate each file immediately after

### cache writer
- records a completed extraction in a cache manifest
- stores what rate was extracted, how many frames, time range, storage prefix
- enables the frame cache index to answer future requests without scanning storage

### data evaluator *(planned)*
- plots sensor data *(time-series of depth, temperature, etc.)* so you can see what happened during a dive
- outputs selections as time windows and environmental conditions ready to feed into the extraction planner

### map viewer *(planned)*
- plots frame positions on an interactive map using embedded geospatial metadata
