import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", css_file="theme-08.css")


@app.cell
def _():
    import marimo as mo
    import subprocess
    import yaml
    import csv
    import json
    import re
    import pandas as pd
    import matplotlib.pyplot as plt
    from itertools import islice
    from pathlib import Path
    from PIL import Image, ExifTags

    VIDEOS = "./EX-clips/"
    DATA = "ex2503_dive01_sensors.csv"

    def plan_cmd(spec_file):
        return ["uv", "run", "deep-framex", VIDEOS,
                "--spec", spec_file, "--data", DATA, "--plan"]

    def run_cmd(spec_file):
        return ["uv", "run", "deep-framex", VIDEOS,
                "--spec", spec_file, "--data", DATA]

    def bounds(spec, column):
        """First min/max pair constraining `column` anywhere in the spec's rules."""
        for rule in spec.get("rules", []):
            for c in rule.get("constraints", []):
                if c.get("column") == column:
                    return c.get("min"), c.get("max")
        return None, None

    return (
        DATA,
        ExifTags,
        Image,
        Path,
        bounds,
        csv,
        islice,
        json,
        mo,
        pd,
        plan_cmd,
        plt,
        re,
        run_cmd,
        subprocess,
        yaml,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Extraction Playground

    NOAA Ship *Okeanos Explorer* EX2503, dive 01, 11 April 2025. Three 5-minute ROV clips, the dive's CTD record, and the vehicle nav track combined into one CSV.

    Edit the spec, re-submit, re-plan and see the extraction plots. Confirm, and then extract.
    """)
    return


@app.cell
def _(mo):
    download_button = mo.ui.run_button(label="Download sample videos")
    download_button
    return (download_button,)


@app.cell
def _(download_button, mo, subprocess):
    mo.stop(not download_button.value)

    BASE_URL = "https://www.ncei.noaa.gov/data/oceans/oer/video/EX2503/Video/EX2503_DIVE01_20250411/Compressed"
    FILES = [
        "EX2503_VID_20250411T202459Z_ROVHD_Low.mp4",
        "EX2503_VID_20250411T203000Z_ROVHD_Low.mp4",
        "EX2503_VID_20250411T203459Z_ROVHD_Low.mp4",
    ]

    subprocess.run(["mkdir", "-p", "EX-clips"])

    for name in FILES:
        subprocess.run(
            ["curl", "-fL", "--progress-bar", f"{BASE_URL}/{name}", "-o", f"EX-clips/{name}"],
            check=True,
        )
    mo.md("✅ Sample videos downloaded.")
    return


@app.cell(hide_code=True)
def _(DATA, islice, mo, pd):
    sensors = pd.read_csv(DATA, parse_dates=["utc_time"])

    with open(DATA) as _f:
        _head = "".join(islice(_f, 9))

    mo.md(
        "## The data\n\n"
        f"```\n{_head}```\n\n"
        f"{len(sensors):,} rows at 1 s, {sensors["utc_time"].min():%H:%M:%S}Z to "
        f"{sensors["utc_time"].max():%H:%M:%S}Z. CTD readings with the nav fixes "
        "interpolated onto the same grid.\n\n"
        "Any column here can go in `mappings`, and any mapped column can be constrained."
    )
    return (sensors,)


@app.cell
def _(mo, yaml):
    def check_yaml(value):
        try:
            yaml.safe_load(value["text"])
        except yaml.YAMLError as e:
            return f"Invalid YAML: {e}"
        return None # YAML check passed

    form = (
        mo.md("""
        **YAML:** {text}
        **Filename:** {filename}
        """)
        .batch(
            text=mo.ui.text_area(
                value=(
                    "rules:\n"
                    "  - interval_s: 30.0\n"
                    "    constraints:\n"
                    "    - column: pressure\n"
                    "      min: 1832\n"
                    "      max: 1844\n"
                    "    - column: temperature\n"
                    "      min: 2.17\n"
                    "      max: 2.24\n"
                    "\n"
                    "mappings:\n"
                    "  timestamp: utc_time\n"
                    "  latitude: latitude\n"
                    "  longitude: longitude\n"
                    "  pressure: pressure_dbar\n"
                    "  temperature: temperature_c\n"
                    "  turbidity: turbidity_ftu\n"
                    "\n"
                    "video_start_times:\n"
                    "  \"EX2503_VID_20250411T202459Z_ROVHD_Low.mp4\": \"2025-04-11T20:24:59Z\"\n"
                    "  \"EX2503_VID_20250411T203000Z_ROVHD_Low.mp4\": \"2025-04-11T20:30:00Z\"\n"
                    "  \"EX2503_VID_20250411T203459Z_ROVHD_Low.mp4\": \"2025-04-11T20:34:59Z\"\n"
                    "\n"
                    "metadata:\n"
                    "  cruise_id: EX2503\n"
                    "  dive_id: DIVE01\n"
                    "\n"
                    "filename_template: \"{utc}_{video_stem}.jpg\""
                ),
                rows=24,
            ),
            filename=mo.ui.text(value="extraction_spec.yaml"),
        )
        .form(validate=check_yaml)
    )
    form
    return (form,)


@app.cell
def _(form, mo, yaml):
    if form.value:
        _contents = yaml.safe_load(form.value["text"])
        with open(form.value["filename"], "w") as _f:
            yaml.safe_dump(_contents, _f, sort_keys=False)
        _saved = mo.md(
            f"Saved to `{form.value["filename"]}`. "
            "`conductivity_sm`, `oxygen_raw_v` and `orp` are in the CSV too, if you want more to constrain on."
        )
    else:
        _saved = mo.md("Submit the form above to write the spec file.")
    _saved
    return


@app.cell
def _(form, mo, plan_cmd):
    plan_button = mo.ui.run_button(label="Run plan")

    _name = form.value["filename"] if form.value else "extraction_spec.yaml"
    mo.vstack([
        mo.md(f"```bash\n{" ".join(plan_cmd(_name))}\n```"),
        plan_button,
    ])
    return (plan_button,)


@app.cell
def _(form, mo, pd, plan_button, plan_cmd, re, subprocess, yaml):
    mo.stop(not form.value, mo.md("Submit the spec form above first."))

    with open(form.value["filename"]) as _f:
        spec = yaml.safe_load(_f)

    # The plots below read planned_times, so it is always defined — empty until
    # the button is clicked. That way the plots draw as soon as a spec is saved.
    if plan_button.value:
        _result = subprocess.run(
            plan_cmd(form.value["filename"]), capture_output=True, text=True
        )
        _output = _result.stdout + _result.stderr
        # Pull the UTC stamp off each planned frame line to mark them on the plots.
        planned_times = pd.to_datetime(
            re.findall(r"^\s+(\S+)\s+offset=", _output, re.M), utc=True
        )
        _shown = mo.md(f"```\n{_output}\n```")
    else:
        planned_times = pd.DatetimeIndex([], tz="UTC")
        _shown = mo.md("Click **Run plan** to see what this spec would extract.")
    _shown
    return planned_times, spec


@app.cell
def _(pd, planned_times, plt, sensors):
    VIDEO_START = pd.Timestamp("2025-04-11T20:24:59Z")
    VIDEO_END = pd.Timestamp("2025-04-11T20:39:59Z")

    _at_frames = sensors.set_index("utc_time").reindex(planned_times, method="nearest")

    fig_profile, _ax = plt.subplots()
    _ax.plot(sensors["utc_time"], sensors["pressure_dbar"], color="steelblue", linewidth=0.8)
    _ax.axvspan(VIDEO_START, VIDEO_END, color="coral", alpha=0.25, label="Video session")
    _ax.plot(planned_times, _at_frames["pressure_dbar"], "o", color="crimson",
             markersize=4, label=f"{len(planned_times)} planned frames")

    _ax.set_ylabel("Pressure (dbar)")
    _ax.tick_params(axis="x", rotation=45)
    _ax.invert_yaxis()
    _ax.legend(loc="center right", fontsize="small")
    fig_profile.suptitle("Dive profile")
    plt.tight_layout()

    fig_profile
    return VIDEO_END, VIDEO_START


@app.cell
def _(VIDEO_END, VIDEO_START, planned_times, plt, sensors):
    _in_video = sensors[(sensors["utc_time"] >= VIDEO_START) & (sensors["utc_time"] <= VIDEO_END)]
    _at_frames = sensors.set_index("utc_time").reindex(planned_times, method="nearest")

    fig_track, _ax = plt.subplots()
    _ax.plot(sensors["longitude"], sensors["latitude"], color="grey", linewidth=0.6, label="Full dive track")
    _ax.plot(_in_video["longitude"], _in_video["latitude"], color="coral", linewidth=2, label="Video session")
    _ax.plot(_at_frames["longitude"], _at_frames["latitude"], "o", color="crimson",
             markersize=4, label="Planned frames")

    _ax.set_xlabel("Longitude")
    _ax.set_ylabel("Latitude")
    _ax.ticklabel_format(useOffset=False)
    _ax.tick_params(axis="x", rotation=45)
    _ax.legend(loc="best", fontsize="small")
    fig_track.suptitle("Vehicle track")
    plt.tight_layout()

    fig_track
    return


@app.cell
def _(VIDEO_END, VIDEO_START, bounds, pd, planned_times, plt, sensors, spec):
    _lo = VIDEO_START - pd.Timedelta(minutes=10)
    _hi = VIDEO_END + pd.Timedelta(minutes=10)
    _near = sensors[(sensors["utc_time"] >= _lo) & (sensors["utc_time"] <= _hi)]
    _at_frames = sensors.set_index("utc_time").reindex(planned_times, method="nearest")

    fig_pt, _ax1 = plt.subplots()
    _ax1.plot(_near["utc_time"], _near["pressure_dbar"], color="steelblue", label="Pressure")
    _ax1.plot(planned_times, _at_frames["pressure_dbar"], "o", color="crimson", markersize=4)
    _ax1.axvspan(VIDEO_START, VIDEO_END, color="coral", alpha=0.15)
    _ax1.set_ylabel("Pressure (dbar)")
    _ax1.tick_params(axis="y", labelcolor="steelblue")
    _ax1.tick_params(axis="x", rotation=45)
    _ax1.invert_yaxis()

    _pmin, _pmax = bounds(spec, "pressure")
    for _b in (_pmin, _pmax):
        if _b is not None:
            _ax1.axhline(_b, color="steelblue", linestyle=":", linewidth=1)

    _ax2 = _ax1.twinx()
    _ax2.plot(_near["utc_time"], _near["temperature_c"], color="darkorange", label="Temperature")
    _ax2.set_ylabel("Temperature (°C)")
    _ax2.tick_params(axis="y", labelcolor="darkorange")

    _tmin, _tmax = bounds(spec, "temperature")
    for _b in (_tmin, _tmax):
        if _b is not None:
            _ax2.axhline(_b, color="darkorange", linestyle=":", linewidth=1)

    fig_pt.suptitle("Pressure and temperature — dotted lines are your constraints")
    plt.tight_layout()

    fig_pt
    return


@app.cell
def _(form, mo, run_cmd):
    run_button = mo.ui.run_button(label="Run extraction")

    _name = form.value["filename"] if form.value else "spec_08.yaml"
    mo.vstack([
        mo.md(f"```bash\n{" ".join(run_cmd(_name))}\n```"),
        run_button,
    ])
    return (run_button,)


@app.cell
def _(form, mo, run_button, run_cmd, subprocess):
    mo.stop(not run_button.value)
    mo.stop(not form.value, mo.md("Submit the spec form above first."))

    # Clear any frames from a previous run so results don't mix together.
    subprocess.run(["rm", "-rf", "frames/"])

    _result = subprocess.run(
        run_cmd(form.value["filename"]), capture_output=True, text=True
    )

    if _result.returncode == 0:
        _message = mo.md("✅ **Done!** Your frames have been extracted.")
    else:
        _message = mo.md(f"⚠️ **Something went wrong.** Here is what deep-framex reported:\n\n```\n{_result.stdout + _result.stderr}\n```")
    _message
    return


@app.cell(hide_code=True)
def _(mo):
    mo.vstack([
        mo.Html('<hr style="height:6px;border:0;margin:3rem 0 1rem;'
                'background:light-dark(rgba(0,0,0,0.35),rgba(255,255,255,0.35))">'),
        mo.md("""
    # Examine Your Frames

    Click reload after each extraction.
        """),
    ])
    return


@app.cell
def _(mo):
    reload_button = mo.ui.refresh(label="Reload frames after running a new extraction:")
    reload_button
    return (reload_button,)


@app.cell
def _(Path, mo, reload_button):
    reload_button  # re-run this cell whenever the reload button is clicked

    _images = sorted(
        p for p in Path("frames").glob("*") if p.suffix.lower() in {".jpg", ".jpeg"}
    )

    mo.stop(
        not _images,
        mo.md("⚠️ No images found in `frames/`. Run an extraction first."),
    )

    _preview = [mo.image(src=str(img), width=200) for img in _images]

    # Flexible grid: up to 4 per row
    COLS = 4
    _preview_rows = [
        mo.hstack(_preview[i : i + COLS], justify="start")
        for i in range(0, len(_preview), COLS)
    ]

    filename = mo.ui.dropdown(
        options={p.name: str(p) for p in _images},
        value=_images[0].name,
        label="Select image to render metadata below:",
    )
    mo.vstack([
        mo.md("## Preview images"),
        *_preview_rows,
        mo.md("## Metadata"),
        filename,
        ])
    return (filename,)


@app.cell
def _(ExifTags, Image, filename, mo):
    mo.stop(not filename.value, mo.md("Select a frame above."))

    with Image.open(filename.value) as _img:
        _exif = _img.getexif()

    # Pointer tags to the sub-IFDs — offsets, not real data.
    _pointer_tags = {ExifTags.IFD.Exif, ExifTags.IFD.GPSInfo}

    # Top-level IFD0 tags (Make, Model, ...).
    exif_data = {
        ExifTags.TAGS.get(tag, tag): value
        for tag, value in _exif.items()
        if tag not in _pointer_tags
    }

    # DateTimeOriginal and friends live in the Exif sub-IFD.
    _exif_ifd = _exif.get_ifd(ExifTags.IFD.Exif)
    exif_data.update(
        {ExifTags.TAGS.get(tag, tag): value for tag, value in _exif_ifd.items()}
    )

    # GPS coordinates / depth live in the GPS IFD.
    _gps_ifd = _exif.get_ifd(ExifTags.IFD.GPSInfo)
    if _gps_ifd:
        exif_data["GPS"] = {
            ExifTags.GPSTAGS.get(tag, tag): value for tag, value in _gps_ifd.items()
        }

    mo.vstack([
        mo.md("""
        ### **EXIF metadata**

        Includes GPS latitude, longitude and timestamp, embedded in each image.
        """),
        exif_data,
    ])
    return


@app.cell
def _(Path, csv, mo, reload_button):
    reload_button  # re-run this cell whenever the reload button is clicked

    mo.stop(
        not Path("frames/biigle_metadata.csv").exists(),
        mo.md("Run an extraction to generate `frames/biigle_metadata.csv`."),
    )

    with open("frames/biigle_metadata.csv", newline="", encoding="utf-8") as _f:
        _biigle_rows = list(csv.DictReader(_f))

    mo.vstack([
        mo.md("""
        ### **BIIGLE metadata**
        Along with the frames we generate a BIIGLE-formatted metadata csv, which you can use to import metadata alongside your images in the BIIGLE interface.
        """),
        mo.ui.table(_biigle_rows, selection=None, show_search=False, show_download=False),
    ])
    return


@app.cell
def _(Path, json, mo, reload_button):
    reload_button  # re-run this cell whenever the reload button is clicked

    mo.stop(
        not Path("frames/ifdo.json").exists(),
        mo.md("Run an extraction to generate `frames/ifdo.json`."),
    )

    with open("frames/ifdo.json", "r", encoding="utf-8") as _j:
        _ifdo = json.load(_j)

    mo.vstack([
        mo.md("""
        ### **IFDO metadata**
        The `ifdo.json` file holds metadata for all generated images following the IFDO specification in JSON structure.
        """),
        mo.json(_ifdo, label="IFDO JSON metadata"),
    ])
    return


if __name__ == "__main__":
    app.run()
