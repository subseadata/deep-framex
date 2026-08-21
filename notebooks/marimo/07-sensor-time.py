import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium", css_file="theme-04.css")


@app.cell
def _():
    import marimo as mo
    import subprocess
    import yaml
    import pandas as pd
    import matplotlib.pyplot as plt
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

    return mo, pd, plt, subprocess, yaml, yaml_block


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Aligning Sensor Time

    In the last notebook we fixed the *video* clock. Now we fix the *sensor* clock.

    Sensor loggers get their time set by hand, and hands make mistakes. A logger set to ship local time instead of UTC, a clock never synced after a power cycle, a data system that stamps rows when it writes them rather than when it read them — any of these leaves you with sensor data whose timestamps are wrong by a fixed amount.

    This one is more dangerous than a bad video clock. A video with no start time makes deep-framex stop and tell you. A sensor file with a wrong-but-valid clock extracts perfectly happily and quietly attaches the wrong readings to every frame.

    We'll use the same three *Okeanos Explorer* clips from notebook 06. If you already downloaded them, the button below is a no-op.

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
    ## The sensor file

    `ex2503_rovctd.csv` is the CTD record from the same dive as the video — the real instrument, converted from the Sea-Bird `.cnv` cast that came off the vehicle. Six channels, one reading per second, running for nearly eight hours. Notebook 08 covers what that conversion involved; the converter is `cnv_to_csv.py`, next to this notebook.

    Its clock is correct. So to have a problem to solve, we're going to break one on purpose: the cell below writes a copy whose timestamps are all three minutes late, as if the logger had been running three minutes fast. **That copy is your "as received" file** — pretend a colleague handed it to you and said nothing about it.

    """)
    return


@app.cell
def _(mo, pd):
    ctd = pd.read_csv("ex2503_rovctd.csv", parse_dates=["utc_time"])

    CLOCK_ERROR = pd.Timedelta(minutes=3)
    _fast = ctd.copy()
    _fast["utc_time"] = (_fast["utc_time"] + CLOCK_ERROR).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    _fast.to_csv("_rovctd_fastclock.csv", index=False)

    mo.md(f"""
    Wrote `_rovctd_fastclock.csv` — {len(_fast):,} rows, every timestamp {CLOCK_ERROR.seconds // 60} minutes later than the truth.

    | | first reading | last reading |
    |---|---|---|
    | true record | {ctd["utc_time"].min():%H:%M:%S}Z | {ctd["utc_time"].max():%H:%M:%S}Z |
    | as received | {ctd["utc_time"].min() + CLOCK_ERROR:%H:%M:%S}Z | {ctd["utc_time"].max() + CLOCK_ERROR:%H:%M:%S}Z |
    """)
    return CLOCK_ERROR, ctd


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## What the offset looks like

    Below is the pressure trace as the received file stamps it, against the shaded 15 minutes the video covers. The vehicle is near bottom and slowly shallowing, so the curve has a shape you can read — and that shape sits three minutes to the right of where it belongs.

    """)
    return


@app.cell
def _(CLOCK_ERROR, ctd, pd, plt):
    VIDEO_START = pd.Timestamp("2025-04-11T20:24:59Z")
    VIDEO_END = pd.Timestamp("2025-04-11T20:39:59Z")

    # Zoom to the video session plus a few minutes either side; across the full
    # eight-hour cast a three-minute offset is invisible.
    _lo = VIDEO_START - pd.Timedelta(minutes=10)
    _hi = VIDEO_END + pd.Timedelta(minutes=10)
    _near = ctd[(ctd["utc_time"] >= _lo) & (ctd["utc_time"] <= _hi)]

    fig, ax1 = plt.subplots()
    ax1.plot(_near["utc_time"] + CLOCK_ERROR, _near["pressure_dbar"],
             color="steelblue", label="Pressure, as received")
    ax1.plot(_near["utc_time"], _near["pressure_dbar"],
             color="steelblue", alpha=0.35, linestyle="--", label="Pressure, true time")
    ax1.axvspan(VIDEO_START, VIDEO_END, color="coral", alpha=0.15, label="Video session")

    ax1.set_ylabel("Pressure (dbar)")
    ax1.tick_params(axis="x", rotation=45)
    ax1.invert_yaxis()
    ax1.legend(loc="lower left", fontsize="small")
    fig.suptitle("The same trace, three minutes apart")
    plt.tight_layout()

    fig
    return VIDEO_END, VIDEO_START


@app.cell(hide_code=True)
def _(CLOCK_ERROR, ctd, mo):
    mo.md(f"""
    ## How would you know?

    In the plot above we cheated — we drew the true trace as well, because we made the error ourselves. With a file someone handed you, you get the solid line only, and nothing about it looks wrong.

    So which one is off, and by how much? **You have to know.** That knowledge comes from outside the data:

    - the dive log records when the CTD started logging, or when the vehicle left the surface
    - the sensor system and the recorder were started together, so the first reading pairs with the first frame
    - something visible in the video has a known time — a slate, an overlay, an event radioed in
    - the logger is known to have run on ship local time, a whole number of hours out

    For this dive, take it as known from the dive log that the CTD began logging at **{ctd["utc_time"].min():%H:%M:%S}Z**. The received file claims its first reading was at {ctd["utc_time"].min() + CLOCK_ERROR:%H:%M:%S}Z. There are your three minutes.

    Worth noticing: the CTD started logging nearly two hours before the first clip rolls. That's normal — instruments come on before cameras do. So "first reading" and "first frame" are *not* the same moment here, and a correction that assumed they were would be wrong by that two hours.

    """)
    return


@app.cell(hide_code=True)
def _(mo, yaml_block):
    mo.vstack([
        mo.md("""
    ## Two ways to say it

    deep-framex gives you two spec keys, and you pick whichever matches what you actually know.

    If you know **how far off the clock was**, shift it. The value is a signed `HH:MM:SS` duration added to every sensor timestamp — negative to wind the clock back:
        """),
        yaml_block("""
    sensor_time_shift: "-00:03:00"
        """),
        mo.md("""
    If instead you know **when the first reading was really taken**, say that, and let deep-framex work out the shift:
        """),
        yaml_block("""
    sensor_start_time: "2025-04-11T18:48:44Z"
        """),
        mo.md("""
    For this file the two are the same correction expressed two ways, and they produce identical output. Use whichever matches the fact you have — guessing a duration when you know a time is how you end up off by a bit.

    `sensor_start_time` anchors the **earliest reading in the file** — not the first row, and not the first video frame. The file doesn't need to be sorted, and the reading being anchored can sit hours before any footage, as it does here.

    Two things to keep in mind:

    - **Quote the value.** YAML has an old habit of reading colon-separated numbers as base-60: unquoted, `1:30:00` becomes the integer 5400. Zero-padding happens to dodge it — `01:30:00` stays a string — but don't rely on that. deep-framex rejects a number here rather than guessing, so the failure is loud, not silent.
    - **They are mutually exclusive.** Setting both is an error, on purpose. They can disagree, and there is no sensible way to pick a winner.

    Both keys move the whole log rigidly — the spacing between readings is untouched. Neither corrects clock *drift*, where the logger gains or loses time as it goes. If your clock drifted, a single shift is the wrong tool.

    Here is the full spec. `video_start_times` is what we built in notebook 06 and `mappings` follows notebook 04 — the only new line is the shift:
        """),
        yaml_block("""
    rules:
      - interval_s: 30.0
        constraints:
          - column: pressure
            min: 1841

    sensor_time_shift: "-00:03:00"

    video_start_times:
      "EX2503_VID_20250411T202459Z_ROVHD_Low.mp4": "2025-04-11T20:24:59Z"
      "EX2503_VID_20250411T203000Z_ROVHD_Low.mp4": "2025-04-11T20:30:00Z"
      "EX2503_VID_20250411T203459Z_ROVHD_Low.mp4": "2025-04-11T20:34:59Z"

    mappings:
      timestamp: utc_time
      pressure: pressure_dbar
      temperature: temperature_c
        """),
        mo.md("""
    The constraint asks for a frame every 30 seconds while the vehicle was below 1841 dbar — the deepest stretch of this window, which the trace passes through early and then leaves behind. That makes the alignment easy to judge: get it right and the frames come from when the vehicle was actually down there.
        """),
    ])
    return


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
                    "      - column: pressure\n"
                    "        min: 1841\n"
                    "\n"
                    "sensor_time_shift: \"-00:03:00\"\n"
                    "\n"
                    "video_start_times:\n"
                    "  \"EX2503_VID_20250411T202459Z_ROVHD_Low.mp4\": \"2025-04-11T20:24:59Z\"\n"
                    "  \"EX2503_VID_20250411T203000Z_ROVHD_Low.mp4\": \"2025-04-11T20:30:00Z\"\n"
                    "  \"EX2503_VID_20250411T203459Z_ROVHD_Low.mp4\": \"2025-04-11T20:34:59Z\"\n"
                    "\n"
                    "mappings:\n"
                    "  timestamp: utc_time\n"
                    "  pressure: pressure_dbar\n"
                    "  temperature: temperature_c"
                ),
                rows=18,
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
        _saved = mo.md(f"Saved to `{form.value["filename"]}`")
    else:
        _saved = mo.md("Submit the form above to write the spec file.")
    _saved
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Check before you extract

    Decoding video is the slow, expensive part of a run, and a misaligned sensor clock produces frames that look completely fine. So don't extract first. Ask deep-framex what it *intends* to do:

    ```bash
    uv run deep-framex ./EX-clips/ --spec extraction_spec.yaml --data _rovctd_fastclock.csv --plan
    ```

    The `--plan` flag walks the whole pipeline except the decoding. It prints every frame it would extract, with its UTC timestamp and the sensor values it would attach — in seconds, without writing anything.

    The button below runs it twice against the received file: once with the shift stripped out of your spec, once with it left in.

    """)
    return


@app.cell
def _(mo):
    plan_button = mo.ui.run_button(label="Compare plans")
    plan_button
    return (plan_button,)


@app.cell
def _(form, mo, plan_button, subprocess, yaml):
    mo.stop(not plan_button.value)
    mo.stop(not form.value, mo.md("Submit the spec form above first."))

    with open(form.value["filename"]) as _f:
        spec = yaml.safe_load(_f)

    # Strip both alignment keys to get the "uncorrected clock" version of the spec.
    unaligned = {k: v for k, v in spec.items()
                 if k not in ("sensor_time_shift", "sensor_start_time")}

    def run_plan(spec_dict, path):
        with open(path, "w") as _out:
            yaml.safe_dump(spec_dict, _out, sort_keys=False)
        result = subprocess.run(
            ["uv", "run", "deep-framex", "./EX-clips/",
             "--spec", path, "--data", "_rovctd_fastclock.csv", "--plan"],
            capture_output=True,
            text=True,
        )
        return result.stdout

    before = run_plan(unaligned, "_plan_unaligned.yaml")
    after = run_plan(spec, "_plan_aligned.yaml")

    mo.hstack([
        mo.vstack([mo.md("### Sensor clock left wrong"), mo.md(f"```\n{before}\n```")]),
        mo.vstack([mo.md("### Sensor clock corrected"), mo.md(f"```\n{after}\n```")]),
    ], widths="equal")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Read the difference

    The uncorrected run finds **14 frames across two clips**, running out to 20:31:29. The corrected run finds **8, all inside the first clip**, ending at 20:28:29.

    Look at what that means. The error didn't merely attach slightly wrong numbers — it changed *which frames exist*. Asked for footage of the vehicle below 1841 dbar, the uncorrected run handed back six frames from after it had already risen above that depth, because it was reading pressures from three minutes earlier. Every one of those frames is mislabelled, and nothing in the output says so.

    There's a detail worth checking by eye. The corrected run's first frame reads `pressure=1842.779`. Find that same number in the uncorrected column — it's there, on the frame at 20:27:59. Exactly three minutes later, which is the error, showing up in the data precisely where you'd predict. That's the correction working, and it's the kind of check worth making on your own data.

    Neither run printed a warning. Neither failed. The only thing separating the good output from the bad one is a person knowing what the sensor clock was doing.

    Now run it for real.

    """)
    return


@app.cell
def _(mo):
    run_button = mo.ui.run_button(label="Run extraction")
    run_button
    return (run_button,)


@app.cell
def _(mo, run_button, subprocess):
    # Wait until the button is clicked before running anything.
    mo.stop(not run_button.value)

    # Clear any frames from a previous run so results don't mix together.
    # "-f" makes this a no-op (no error) when frames/ doesn't exist yet.
    subprocess.run(["rm", "-rf", "frames/"])

    result = subprocess.run(
        ["uv", "run", "deep-framex", "./EX-clips/", "--spec", "extraction_spec.yaml",
         "--data", "_rovctd_fastclock.csv"],
        capture_output=True,
        text=True,
    )

    output = result.stdout + result.stderr
    if result.returncode == 0:
        message = mo.md(f"✅ **Done!** Your frames have been extracted.")
    else:
        message = mo.md(f"⚠️ **Something went wrong.** Here is what deep-framex reported:\n\n```\n{output}\n```")
    message
    return


if __name__ == "__main__":
    app.run()
