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

    This one is more dangerous than a bad video clock. A video with no start time makes deep-framex stop and tell you. A sensor file with a wrong-but-valid clock extracts perfectly happily and quietly attaches the wrong depth, the wrong position, and the wrong temperature to every frame.

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

    Alongside the video there is a sensor log, `ex2503_sensor.csv`, with a reading every 15 seconds. It's a plain timestamped CSV like the one in notebook 04 — a `time` column plus depth and temperature.

    A note on honesty: the video clips are real NOAA footage, but this sensor file is **made up** for the exercise. The dive profile in it — descend, work the bottom, come back up — is shaped so you can see the alignment problem, not to describe anything that actually happened on EX2503.

    Let's plot it.

    """)
    return


@app.cell
def _(pd, plt):
    df = pd.read_csv("ex2503_sensor.csv")
    df["time"] = pd.to_datetime(df["time"])

    fig, ax1 = plt.subplots()

    ax1.plot(df["time"], df["depth_m"], color="steelblue", label="Depth")
    ax1.set_ylabel("Depth (m)")
    ax1.tick_params(axis="y", labelcolor="steelblue")
    ax1.tick_params(axis="x", rotation=45)
    ax1.legend(loc="upper left")

    # The video session runs 20:24:59 -> 20:39:59. Mark it so the offset is visible.
    ax1.axvspan(
        pd.Timestamp("2025-04-11T20:24:59"),
        pd.Timestamp("2025-04-11T20:39:59"),
        color="coral", alpha=0.15, label="Video session",
    )
    ax1.legend(loc="upper left")

    fig.suptitle("Sensor log, as timestamped, against the video session")
    ax1.invert_yaxis()
    plt.tight_layout()

    fig
    return (df,)


@app.cell(hide_code=True)
def _(df, mo):
    mo.md(f"""
    ## Spotting the offset

    The sensor log runs from **{df["time"].min():%H:%M:%S}Z to {df["time"].max():%H:%M:%S}Z**. The video session runs from **20:24:59Z to 20:39:59Z**. They overlap, but they don't line up — the sensor log starts three minutes after the video does and keeps running three minutes past the end of it.

    Which one is wrong? Nothing in either file will tell you. This is the part no tool can do for you: **you have to know.** In practice that knowledge comes from somewhere outside the data —

    - the dive log says the ROV left the surface at a recorded UTC time
    - the sensor system was started at the same moment as the recorder, so the first reading belongs at the first frame
    - something visible in the video has a known time — a slate, a timestamp overlay, an event radioed in
    - the logger is known to have been running on ship local time, a whole number of hours out

    For this dive, take it as known that the CTD started logging the instant the recorder rolled: **the first sensor reading belongs at 20:24:59Z**, the start of the first clip. The log says 20:27:59Z. The logger was three minutes fast.

    """)
    return


@app.cell(hide_code=True)
def _(mo, yaml_block):
    mo.vstack([
        mo.md("""
    ## Two ways to say it

    deep-framex gives you two spec keys for this, and you pick whichever matches what you actually know.

    If you know **how far off the clock was**, shift it. The value is a signed `HH:MM:SS` duration, added to every sensor timestamp — negative to wind the clock back:
        """),
        yaml_block("""
    sensor_time_shift: "-00:03:00"
        """),
        mo.md("""
    If instead you know **when the first reading was really taken**, say that, and let deep-framex work out the shift:
        """),
        yaml_block("""
    sensor_start_time: "2025-04-11T20:24:59Z"
        """),
        mo.md("""
    For this file the two are the same correction expressed two ways, and they produce identical output. Use whichever matches the fact you have — guessing a duration when you know a time is how you end up off by a bit.

    Two things to keep in mind:

    - **Quote the value.** YAML has an old habit of reading colon-separated numbers as base-60: unquoted, `1:30:00` becomes the integer 5400. Zero-padding happens to dodge it — `01:30:00` stays a string — but don't rely on that. deep-framex rejects a number here rather than guessing, so the failure is loud, not silent.
    - **They are mutually exclusive.** Setting both is an error, on purpose. They can disagree, and there is no sensible way to pick a winner.

    Both keys move the whole log rigidly — the spacing between readings is untouched. Neither one corrects clock *drift*, where the logger gains or loses time as it goes. If your clock drifted, a single shift is the wrong tool.

    Here is the full spec. The `video_start_times` block is the one we built in notebook 06, and `mappings` is from notebook 04 — the only new line is the shift:
        """),
        yaml_block("""
    rules:
      - interval_s: 30.0
        constraints:
          - column: depth
            min: 1502

    sensor_time_shift: "-00:03:00"

    video_start_times:
      "EX2503_VID_20250411T202459Z_ROVHD_Low.mp4": "2025-04-11T20:24:59Z"
      "EX2503_VID_20250411T203000Z_ROVHD_Low.mp4": "2025-04-11T20:30:00Z"
      "EX2503_VID_20250411T203459Z_ROVHD_Low.mp4": "2025-04-11T20:34:59Z"

    mappings:
      timestamp: time
      depth: depth_m
      temperature: temperature
        """),
        mo.md("""
    The constraint asks for a frame every 30 seconds while the ROV was below 1502 m — the deepest part of the profile. That makes the alignment easy to check: get it right and the frames come from the moment the vehicle was actually down there.
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
                    "      - column: depth\n"
                    "        min: 1502\n"
                    "\n"
                    "sensor_time_shift: \"-00:03:00\"\n"
                    "\n"
                    "video_start_times:\n"
                    "  \"EX2503_VID_20250411T202459Z_ROVHD_Low.mp4\": \"2025-04-11T20:24:59Z\"\n"
                    "  \"EX2503_VID_20250411T203000Z_ROVHD_Low.mp4\": \"2025-04-11T20:30:00Z\"\n"
                    "  \"EX2503_VID_20250411T203459Z_ROVHD_Low.mp4\": \"2025-04-11T20:34:59Z\"\n"
                    "\n"
                    "mappings:\n"
                    "  timestamp: time\n"
                    "  depth: depth_m\n"
                    "  temperature: temperature"
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
    uv run deep-framex ./EX-clips/ --spec extraction_spec.yaml --data ex2503_sensor.csv --plan
    ```

    The `--plan` flag walks the whole pipeline except the decoding. It prints every frame it would extract, with its UTC timestamp and the sensor values it would attach — in seconds, without writing anything.

    The button below runs it twice: once with the shift stripped out of your spec, once with it left in. Compare them.

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
             "--spec", path, "--data", "ex2503_sensor.csv", "--plan"],
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

    Both runs found six frames. Both attached the same depths, around 1502–1504 m. Neither printed a warning. Left uncorrected, the run **succeeds** — it just takes its frames from around 20:33:29–20:35:59, three minutes after the vehicle was actually at that depth, and spread across two clips instead of one.

    That is the whole point of this notebook. There was no error to catch. The only thing separating the good output from the bad one is a person knowing what the sensor clock was doing.

    A useful sanity check when you do have a reference: extraction is the *only* thing shifted here, so anything you can verify against the video itself — a depth readout burned into the frame, a known event — should now agree with the sensor value on that frame. If it doesn't, your shift is wrong or the offset wasn't constant.

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
         "--data", "ex2503_sensor.csv"],
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
