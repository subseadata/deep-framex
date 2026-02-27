# soi-frame-extractor

Frame extraction library for deep sea video.  Frames are self-describing — metadata is embedded directly into image files so context travels with the frame into any downstream system.

## Installation and Use

...

## Structure

```
src/soi_frame_extractor/
├── models/          # pydantic data models
├── config/          # YAML spec parsing and video file discovery
├── data/            # CSV import, clean process, plot data for selection
├── planning/        # translate intervals, periods, sensor constraints into extraction input
├── extraction/      # read frames from video or pre-computed cache
├── cache/           # handles cache sampling and indexing functions
├── metadata/        # attach metadata and geospatial data to frames
├── output/          # write frames to disk or cloud storage
├── analysis/        # score frames for analysis or quality
├── viz/             # frame overlay, map view
└── utils/           # shared helpers (time conversion, image format)
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
- loads CSV files from local path or cloud URI
- parses and validates timestamp column
- returns a time-indexed dataset for use in planning and enrichment
- no assumptions about what columns are present beyond a timestamp

### timestamp correlator
- aligns separate time references into one: sensor/data UTC, video UTC, video time *(t=0 at start->end)*
- everything downstream depends on this being right [how do we handle bad sync events? manual override?]
- alignment point:
    - assume video is authoritative? 

### user ingress
- accepts a YAML config file defining one or more extraction rules (interval + optional UTC time periods)
- accepts video source as either a directory or an explicit list of file paths
- validates all datetimes as ISO 8601 UTC; rejects naive timestamps
- resolves video paths and probes each file for metadata (utc_start, duration)
- produces an ExtractionSpec and VideoSession ready for the planner

### extraction planner
- converts intervals, periods, fps, and data constraint to an extraction spec, then to timestamps 
- all the logic for intervals, time windows, environmental conditions, and combinations lives here
- checks the frame cache first — if pre-computed frames exist at the right rate, get those instead of extracting new ones from video
- the extractor never sees rules, only timestamps

### extractor
- reads frames at the timestamps the planner provides
- single responsibility: get the frame at time T
- async frame extraction *(i.e., don't load all frames into memory at once for a long dive)*

### cache sampler
- used when the extraction planner finds a cache hit
- subsamples pre-cached high-frequency frameset for coarser intervals *(e.g., a request for 1 every 10 seconds just filters a cached 1fps set)*

### cache indexer
- checks whether a video already has pre-computed frames at a given rate
- reads a cache manifest from storage
- returns which requested timestamps are available and which need extraction

### metadata collector
- gathers contextual values for a frame: timestamp, dive ID, cruise ID, vehicle, sensor values at that moment
- interpolates sensor readings to the frame's exact timestamp from the imported dataset? *(would need user choice on interpolation scheme)*
- returns a structured record — knows nothing about image files

### geo interpolator
- takes position log and a UTC timestamp, returns lat/lon/heading at that moment
- pure interpolation — writing GPS tags into the image is the metadata writer's job

### metadata writer
- embeds a frame's metadata record into the image file
- three layers:
  - EXIF GPS tags *(lat, lon, depth, timestamp - JSON string could go into user comment, but XMP might be better)*
  - IPTC fields *(title, keywords, standardized caption w/ credit)*
  - XMP fields *(data fields, needs definition)*

### frame writer
- writes a frame image to storage (local or cloud)
- sets output format *(JPEG, PNG, TIFF)* and quality/compression
- filename generated from a template string *(e.g., `{dive_id}_{depth_m}m_T{utc}.jpg`)*
- returns the storage location of the written file if cloud hosted

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
