import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium", css_file="theme-08.css")


@app.cell
def _():
    import marimo as mo
    import subprocess
    import yaml
    import glob
    import os
    import pandas as pd
    import xml.etree.ElementTree as ET
    from PIL import Image
    import html as _html
    from textwrap import dedent

    def yaml_block(code):
        # Render YAML as a code block via mo.Html so it bypasses marimo's
        # markdown preprocessor, which otherwise rewrites the indentation of
        # any line starting with "- " (YAML sequence items) and breaks the spec.
        body = _html.escape(dedent(code).strip("\n"))
        style = (
            "border:1px solid light-dark(rgba(0,0,0,0.15),rgba(255,255,255,0.18));"
            "background:light-dark(rgba(255,255,255,0.6),rgba(255,255,255,0.05));"
            "border-radius:8px;padding:0.6rem 0.9rem;margin:0.5rem 0;overflow-x:auto;"
        )
        return mo.Html(
            f'<div class="language-yaml codehilite" style="{style}">'
            f'<pre style="margin:0;background:transparent"><span></span>'
            f'<code>{body}</code></pre></div>'
        )

    return ET, Image, glob, mo, os, pd, subprocess, yaml, yaml_block


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # What a Shift Actually Does to Your Frames

    Notebook 07 made the case for aligning sensor time, using a sensor log we made up so the error would be obvious. This one uses the real thing.

    `ex2503_rovctd.csv` is the CTD record from the same *Okeanos Explorer* dive as the video — converted from the Sea-Bird `.cnv` cast that came off the vehicle. It needed real work to get here, and the details are worth knowing because you will hit them with your own instruments:

    - The raw timestamp column is `timeQ`, "Time, NMEA [seconds]" — **seconds since 2000-01-01**, not the Unix epoch. Getting that epoch wrong shifts everything by 30 years, which at least fails loudly.
    - The CTD scans at **24 Hz**, and `timeQ` only records whole seconds. So ~24 rows share every stamp. deep-framex stores readings with the timestamp as a primary key, so duplicates can't be imported at all — the scans within each second are averaged into one reading.
    - Two rows had an NMEA dropout and came through stamped midnight. They were dropped.

    The converter that did all this is `cnv_to_csv.py`, sitting next to this notebook.

    This time we're not correcting an error. We're going to *introduce* one — a five-second shift — and then go read the metadata back out of the extracted JPEGs to see exactly what changed.

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
def _(mo):
    mo.md("""
    ## The CTD record

    Six sensor channels, one row per second, running from well before the video starts to hours after it ends.

    """)
    return


@app.cell
def _(mo, pd):
    ctd = pd.read_csv("ex2503_rovctd.csv", parse_dates=["utc_time"])

    # The three clips cover 20:24:59 -> 20:39:59 on 2025-04-11.
    VIDEO_START = pd.Timestamp("2025-04-11T20:24:59Z")
    VIDEO_END = pd.Timestamp("2025-04-11T20:39:59Z")
    in_video = ctd[(ctd["utc_time"] >= VIDEO_START) & (ctd["utc_time"] <= VIDEO_END)]

    mo.vstack([
        mo.md(f"""
    **{len(ctd):,} rows**, {ctd["utc_time"].min():%Y-%m-%d %H:%M:%S}Z to {ctd["utc_time"].max():%Y-%m-%d %H:%M:%S}Z.
    **{len(in_video):,}** of them fall inside the video session.

    Over those 15 minutes the vehicle sat between **{in_video["pressure_dbar"].min():.1f}** and **{in_video["pressure_dbar"].max():.1f}** dbar — near-bottom, working a site, barely moving. Hold that thought; it decides how visible our shift will be.
        """),
        ctd.head(),
    ])
    return VIDEO_END, VIDEO_START, ctd, in_video


@app.cell(hide_code=True)
def _(mo, yaml_block):
    mo.vstack([
        mo.md("""
    ## The two runs

    Same video, same interval, same mappings — extracted twice. The only difference between the two specs is one line.

    Note `pressure: pressure_dbar`. The CTD reports pressure in decibars, so that is what we call it. deep-framex has a `depth` field that expects metres and routes to standard tags, but pressure is not depth — converting between them needs latitude — and a channel named for what the instrument actually measured beats one named for what we wish it measured. Any mapping name deep-framex doesn't recognise is still carried through in full.
        """),
        yaml_block("""
    rules:
      - interval_s: 45.0

    video_start_times:
      "EX2503_VID_20250411T202459Z_ROVHD_Low.mp4": "2025-04-11T20:24:59Z"
      "EX2503_VID_20250411T203000Z_ROVHD_Low.mp4": "2025-04-11T20:30:00Z"
      "EX2503_VID_20250411T203459Z_ROVHD_Low.mp4": "2025-04-11T20:34:59Z"

    mappings:
      timestamp: utc_time
      pressure: pressure_dbar
      temperature: temperature_c
      turbidity: turbidity_ftu
      orp: orp

    filename_template: "{utc}.jpg"
        """),
        mo.md("""
    The second run adds the shift, and nothing else:
        """),
        yaml_block("""
    sensor_time_shift: "00:00:05"
        """),
        mo.md("""
    A shift moves the *sensor* clock, never the video clock. So both runs plan the identical set of frames at the identical times, with the identical filenames — only the sensor values attached to them can differ. That makes the two runs directly comparable frame by frame.

    Change the shift below if you want to see how the picture changes. Keep it zero-padded — `00:05:00`, not `5:00`.
        """),
    ])
    return


@app.cell
def _(mo):
    shift_input = mo.ui.text(value="00:00:05", label="sensor_time_shift (zero-padded HH:MM:SS)")
    shift_input
    return (shift_input,)


@app.cell
def _(mo):
    run_button = mo.ui.run_button(label="Run both extractions")
    run_button
    return (run_button,)


@app.cell
def _(mo, run_button, shift_input, subprocess, yaml):
    mo.stop(not run_button.value)

    BASE_SPEC = {
        "rules": [{"interval_s": 45.0}],
        "video_start_times": {
            "EX2503_VID_20250411T202459Z_ROVHD_Low.mp4": "2025-04-11T20:24:59Z",
            "EX2503_VID_20250411T203000Z_ROVHD_Low.mp4": "2025-04-11T20:30:00Z",
            "EX2503_VID_20250411T203459Z_ROVHD_Low.mp4": "2025-04-11T20:34:59Z",
        },
        "mappings": {
            "timestamp": "utc_time",
            "pressure": "pressure_dbar",
            "temperature": "temperature_c",
            "turbidity": "turbidity_ftu",
            "orp": "orp",
        },
        "filename_template": "{utc}.jpg",
    }

    def extract_run(spec_dict, spec_path, out_dir):
        subprocess.run(["rm", "-rf", out_dir])
        with open(spec_path, "w") as _out:
            yaml.safe_dump(spec_dict, _out, sort_keys=False)
        return subprocess.run(
            ["uv", "run", "deep-framex", "./EX-clips/", "--spec", spec_path,
             "--data", "ex2503_rovctd.csv", "--output", out_dir],
            capture_output=True, text=True,
        )

    # safe_dump writes the duration unquoted. A zero-padded HH:MM:SS survives that
    # (YAML reads 00:00:05 back as a string), but a bare 5:00 would come back as the
    # sexagesimal integer 300 and deep-framex would reject it. Keep the padding.
    shifted = dict(BASE_SPEC)
    shifted["sensor_time_shift"] = str(shift_input.value)

    r_true = extract_run(BASE_SPEC, "_spec_unshifted.yaml", "frames-unshifted")
    r_shift = extract_run(shifted, "_spec_shifted.yaml", "frames-shifted")

    if r_true.returncode == 0 and r_shift.returncode == 0:
        runs_ok = mo.md("✅ **Both runs finished.**")
    else:
        runs_ok = mo.md(
            "⚠️ **Something went wrong.**\n\n```\n"
            + (r_true.stdout + r_true.stderr + r_shift.stdout + r_shift.stderr)
            + "\n```"
        )
    runs_ok
    return (runs_ok,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Reading the metadata back out

    We could just compare the `ifdo.json` manifests, but those are written from the same in-memory values the extractor used, so they'd prove nothing about the files. Instead we open the JPEGs and read what is actually embedded in them.

    All four of our channels — pressure, temperature, turbidity, orp — live in the custom XMP namespace as `dfx:*`. None of them is a field the image standards have an opinion about, so none gets a dedicated tag. `FIELD_REGISTRY` in `models/core.py` lists the ones that do: map a column to `latitude`, `longitude`, or `depth` and it lands in EXIF GPS tags instead. Everything else falls through to XMP, which is the point of having a custom namespace.

    """)
    return


@app.cell
def _(ET, Image, glob, os, pd, runs_ok):
    # Depend on runs_ok so this cell waits for the extractions.
    runs_ok

    DFX_NS = "{https://deep-framex.org/xmp/v1/}"

    def read_frame_metadata(path):
        values = {"frame": os.path.basename(path)}
        packet = Image.open(path).info["xmp"].decode()
        description = ET.fromstring(packet).find(".//{*}Description")
        for element in description:
            if element.tag.startswith(DFX_NS):
                values[element.tag[len(DFX_NS):]] = float(element.text)
        return values

    def read_run(directory):
        frames = sorted(glob.glob(f"{directory}/*.jpg"))
        return pd.DataFrame([read_frame_metadata(p) for p in frames]).set_index("frame")

    unshifted = read_run("frames-unshifted")
    shifted_run = read_run("frames-shifted")

    CHANNELS = ["pressure", "temperature", "turbidity", "orp"]
    comparison = pd.DataFrame(index=unshifted.index)
    for _channel in CHANNELS:
        comparison[f"{_channel}"] = unshifted[_channel]
        comparison[f"{_channel} (shifted)"] = shifted_run[_channel]
        comparison[f"Δ {_channel}"] = (shifted_run[_channel] - unshifted[_channel]).round(5)

    comparison
    return CHANNELS, comparison, shifted_run, unshifted


@app.cell(hide_code=True)
def _(CHANNELS, comparison, mo, shift_input, unshifted):
    _deltas = comparison[[f"Δ {c}" for c in CHANNELS]]
    _changed = (_deltas.abs() > 0).any(axis=1).sum()
    _rows = [
        f"| {c} | {comparison[f'Δ {c}'].abs().max():.5f} | "
        f"{unshifted[c].max() - unshifted[c].min():.5f} |"
        for c in CHANNELS
    ]

    mo.md(f"""
    ## What changed

    Both runs produced **{len(comparison)}** frames with **identical filenames and identical frame times** — as promised, the shift moved only the sensor clock. Of those, **{_changed}** carry at least one sensor value that differs.

    | channel | largest change from the shift | full range across the 15 min |
    |---|---|---|
    {chr(10).join(_rows)}

    A `{shift_input.value}` shift on this dive is **small**. Every frame moved, but look at the two columns above: the change the shift caused is a small fraction of the range each channel covers anyway. That isn't the feature underperforming — it's the vehicle. It was station-keeping near bottom, so five seconds of sensor time barely moves any of these channels.

    Which is the uncomfortable part. **A misalignment is only as visible as the thing you're measuring is fast.** On a hovering vehicle in stable water, a wrong sensor clock produces metadata that looks perfectly reasonable and is quietly wrong. On a vehicle flying a transect, or crossing a thermocline, or on a winch, the same five seconds would be glaring.

    So don't calibrate your suspicion on how different the numbers look. Push the shift up to `00:05:00` above and re-run: the same mechanism, the same code path, now unmistakable. The mechanism doesn't care about the magnitude — only your ability to notice does.

    """)
    return


if __name__ == "__main__":
    app.run()
