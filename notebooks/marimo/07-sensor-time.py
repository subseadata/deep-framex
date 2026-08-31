import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", css_file="theme-07.css")


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

    In the last notebook we set the video start time by hand. Now we do the same for the sensor clock.

    **Missing video start times will throw an error**. Bad sensor start times will not, and are the scientist's responsibility.

    We'll use the same three *Okeanos Explorer* clips from notebook 06. If you already downloaded them, the button below does no harm.
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

    `ex2503_rovctd.csv` is the CTD record from the same dive as the video, converted from the Sea-Bird `.cnv` cast that came off the vehicle. Its clock is correct.

    `ex2503_rovctd_badclock.csv` is the same dive as it would have come off a vehicle whose clock ran three minutes fast.
    """)
    return


@app.cell
def _(mo, pd):
    ctd = pd.read_csv("ex2503_rovctd.csv", parse_dates=["utc_time"])
    bad = pd.read_csv("ex2503_rovctd_badclock.csv", parse_dates=["utc_time"])

    mo.md(f"""
    {len(ctd):,} rows in each file.

    | | first reading | last reading |
    |---|---|---|
    | `ex2503_rovctd.csv` | {ctd["utc_time"].min():%H:%M:%S}Z | {ctd["utc_time"].max():%H:%M:%S}Z |
    | `ex2503_rovctd_badclock.csv` | {bad["utc_time"].min():%H:%M:%S}Z | {bad["utc_time"].max():%H:%M:%S}Z |
    """)
    return bad, ctd


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## What the offset looks like

    Below is the pressure trace as the received file stamps it, plotted against the shaded 15 minutes the video covers. 
    """)
    return


@app.cell
def _(bad, ctd, pd, plt):
    VIDEO_START = pd.Timestamp("2025-04-11T20:24:59Z")
    VIDEO_END = pd.Timestamp("2025-04-11T20:39:59Z")

    # Zoom to the video session plus a few minutes either side; across the full
    # eight-hour cast a three-minute offset is invisible.
    _lo = VIDEO_START - pd.Timedelta(minutes=10)
    _hi = VIDEO_END + pd.Timedelta(minutes=10)
    _near = ctd[(ctd["utc_time"] >= _lo) & (ctd["utc_time"] <= _hi)]
    _near_bad = bad[(bad["utc_time"] >= _lo) & (bad["utc_time"] <= _hi)]

    fig, ax1 = plt.subplots()
    ax1.plot(_near_bad["utc_time"], _near_bad["pressure_dbar"],
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
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## How would you know?

    deep-framex is not (yet?) a tool for checking the quality of your sensor and camera time records. That responsibility lies with the scientist for now.

    """)
    return


@app.cell(hide_code=True)
def _(mo, yaml_block):
    mo.vstack([
        mo.md("""
    ## Two ways to Solve the Problem

    Both of these describe `ex2503_rovctd_badclock.csv`, the file whose clock ran fast.

    If we know **how far off the clock was**, we shift it. The value is a signed `HH:MM:SS` duration added to every sensor timestamp, negative to wind the clock back:
        """),
        yaml_block("""
    sensor_time_shift: "-00:03:00"
        """),
        mo.md("""
    If instead we know **when the first reading was really taken**, we say that and let deep-framex work out the shift:
        """),
        yaml_block("""
    sensor_start_time: "2025-04-11T18:48:44Z"
        """),
        mo.md("""
    For the bad clock file the two are the same correction written two ways, and they produce identical output. The correct file, `ex2503_rovctd.csv`, needs neither key.

    `sensor_start_time` anchors the **earliest reading in the file** — not the first row, and not the first video frame. The file does not need to be sorted, and the anchored reading can sit hours before any footage, as it does here.

    Neither corrects clock *drift*, where the logger gains or loses time as it goes.

    Here is the full spec:
        """),
        yaml_block("""
    rules:
      - interval_s: 30.0
      constraints:
      - column: pressure
        max: 1841.0

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
                    "    - column: pressure\n"
                    "      max: 1841\n"
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
    ## Plan Mode: Check Before You Extract

    Decoding video is the slow part of a run, and a misaligned sensor clock produces frames that look fine. So before extracting, ask deep-framex what it intends to do:

    ```bash
    # the correct file, with the alignment keys taken out of the spec
    uv run deep-framex ./EX-clips/ --spec _plan_truth.yaml --data ex2503_rovctd.csv --plan

    # the bad clock file, with no correction applied
    uv run deep-framex ./EX-clips/ --spec _plan_uncorrected.yaml --data ex2503_rovctd_badclock.csv --plan

    # the bad clock file, corrected by the spec as you wrote it
    uv run deep-framex ./EX-clips/ --spec _plan_corrected.yaml --data ex2503_rovctd_badclock.csv --plan
    ```

    The `--plan` flag runs the whole pipeline except the decoding. It prints every frame it would extract, with its UTC timestamp and the sensor values it would attach.

    The button below runs all three. The first is the truth we are aiming at; the second is what happens if we run the bad clock data with no correction; the third is what happens when we apply the correction to the bad clock.
    """)
    return


@app.cell
def _(mo):
    plan_button = mo.ui.run_button(label="Run plans")
    plan_button
    return (plan_button,)


@app.cell
def _(form, mo, plan_button, subprocess, yaml):
    mo.stop(not plan_button.value)
    mo.stop(not form.value, mo.md("Submit the spec form above first."))

    with open(form.value["filename"]) as _f:
        spec = yaml.safe_load(_f)

    # Strip both alignment keys. The correct file needs no correction, and the
    # bad clock file with the keys stripped is the uncorrected run.
    unaligned = {k: v for k, v in spec.items()
                 if k not in ("sensor_time_shift", "sensor_start_time")}

    def run_plan(spec_dict, path, data):
        with open(path, "w") as _out:
            yaml.safe_dump(spec_dict, _out, sort_keys=False)
        result = subprocess.run(
            ["uv", "run", "deep-framex", "./EX-clips/",
             "--spec", path, "--data", data, "--plan"],
            capture_output=True,
            text=True,
        )
        return result.stdout

    truth = run_plan(unaligned, "_plan_truth.yaml", "ex2503_rovctd.csv")
    uncorrected = run_plan(unaligned, "_plan_uncorrected.yaml", "ex2503_rovctd_badclock.csv")
    corrected = run_plan(spec, "_plan_corrected.yaml", "ex2503_rovctd_badclock.csv")

    mo.md(
        f"### Correct file, no shift\n```\n{truth}\n```"
        f"\n### Bad clock file, no correction\n```\n{uncorrected}\n```"
        f"\n### Bad clock file, shift applied\n```\n{corrected}\n```"
    )
    
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Note the difference, and the sameness

    The uncorrected run does not just attach slightly wrong numbers, it changes **which frames exist**. We asked for frames when pressure was below 1841 dbar, and moving the sensor clock moves how much video time falls inside that bound.

    The corrected run matches the truth run frame for frame: same timestamps, same sensor values, same set of frames. The shift put the bad file back on the truth.

    None of the three printed a warning and none of them failed.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Extract Both Ways

    Two extractions, one after the other, both writing to `frames/`:

    ```bash
    uv run deep-framex ./EX-clips/ --spec extraction_spec.yaml --data ex2503_rovctd_badclock.csv
    ```

    ```bash
    uv run deep-framex ./EX-clips/ --spec extraction_spec.yaml --data ex2503_rovctd.csv
    ```

    1. Submit the spec form above with `sensor_time_shift` in it, then click the first button.
    2. Open notebook 02 and look at the frames.
    3. Come back, **remove the `sensor_time_shift` line** from the spec form, and submit it again.
    4. Click the second button. It runs against the correct file, and overwrites `frames/`.
    5. Reload notebook 02. Nothing has changed — that is the point.
    """)
    return


@app.cell
def _(mo):
    run_bad_button = mo.ui.run_button(label="Run extraction (bad clock, corrected)")
    run_bad_button
    return (run_bad_button,)


@app.cell
def _(mo, run_bad_button, subprocess):
    mo.stop(not run_bad_button.value)

    # Clear any frames from a previous run so results don't mix together.
    # "-f" makes this a no-op (no error) when frames/ doesn't exist yet.
    subprocess.run(["rm", "-rf", "frames/"])

    _result = subprocess.run(
        ["uv", "run", "deep-framex", "./EX-clips/", "--spec", "extraction_spec.yaml",
         "--data", "ex2503_rovctd_badclock.csv"],
        capture_output=True,
        text=True,
    )

    if _result.returncode == 0:
        _message = mo.md("✅ **Done!** Frames extracted from the bad clock file.")
    else:
        _message = mo.md(f"⚠️ **Something went wrong.** Here is what deep-framex reported:\n\n```\n{_result.stdout + _result.stderr}\n```")
    _message
    return


@app.cell
def _(mo):
    run_good_button = mo.ui.run_button(label="Run extraction (correct file)")
    run_good_button
    return (run_good_button,)


@app.cell
def _(mo, run_good_button, subprocess):
    mo.stop(not run_good_button.value)

    subprocess.run(["rm", "-rf", "frames/"])

    _result = subprocess.run(
        ["uv", "run", "deep-framex", "./EX-clips/", "--spec", "extraction_spec.yaml",
         "--data", "ex2503_rovctd.csv"],
        capture_output=True,
        text=True,
    )

    if _result.returncode == 0:
        _message = mo.md("✅ **Done!** Frames extracted from the correct file.")
    else:
        _message = mo.md(f"⚠️ **Something went wrong.** Here is what deep-framex reported:\n\n```\n{_result.stdout + _result.stderr}\n```")
    _message
    return


if __name__ == "__main__":
    app.run()
