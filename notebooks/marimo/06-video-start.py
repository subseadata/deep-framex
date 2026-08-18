import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium", css_file="theme-01.css")


@app.cell
def _():
    import marimo as mo
    import shutil
    import subprocess
    import yaml
    import html as _html
    from pathlib import Path
    from textwrap import dedent
    from urllib.request import urlretrieve

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

    return Path, mo, shutil, subprocess, urlretrieve, yaml, yaml_block


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Setting Video Start Times

    Many videos do not have start times embedded in the metadata when recorded. To handle this, we provide a VIDEO START TIMES section in the extraction spec. Let's download a sequence of videos from NOAA Ship *Okeanos Explorer*.

    """)
    return


@app.cell
def _(mo):
    download_button = mo.ui.run_button(label="Download sample videos")
    download_button
    return (download_button,)


@app.cell
def _(Path, download_button, mo, urlretrieve):
    mo.stop(not download_button.value)

    BASE_URL = "https://www.ncei.noaa.gov/data/oceans/oer/video/EX2503/Video/EX2503_DIVE01_20250411/Compressed"
    FILES = [
        "EX2503_VID_20250411T202459Z_ROVHD_Low.mp4",
        "EX2503_VID_20250411T203000Z_ROVHD_Low.mp4",
        "EX2503_VID_20250411T203459Z_ROVHD_Low.mp4",
    ]

    dest = Path("EX-clips")
    dest.mkdir(parents=True, exist_ok=True)

    for name in FILES:
        urlretrieve(f"{BASE_URL}/{name}", dest / name)
    mo.md("✅ Sample videos downloaded.")
    return


@app.cell(hide_code=True)
def _(mo, yaml_block):
    mo.vstack([
        mo.md("""
    ## Adding Video Times to Spec

    Our three video files:

    - EX2503_VID_20250411T202459Z_ROVHD_Low.mp4
    - EX2503_VID_20250411T203000Z_ROVHD_Low.mp4
    - EX2503_VID_20250411T203459Z_ROVHD_Low.mp4

    Note that they have a start time in the filename. However, using the ffprobe tool we can see the recorded metadata start time is different than the filename. 

    ```bash
    ❯❯ ffprobe -v error -show_entries format_tags=creation_time -of default=nw=1 EX2503_VID_20250411T202459Z_ROVHD_Low.mp4
        TAG:creation_time=2025-04-11T20:25:59.000000Z
    ❯❯ ffprobe -v error -show_entries format_tags=creation_time -of default=nw=1 EX2503_VID_20250411T203000Z_ROVHD_Low.mp4
        TAG:creation_time=2025-04-11T20:30:57.000000Z
    ❯❯ ffprobe -v error -show_entries format_tags=creation_time -of default=nw=1 EX2503_VID_20250411T203459Z_ROVHD_Low.mp4
        TAG:creation_time=2025-04-11T20:36:00.000000Z
    ```
    For this notebook, it doesn't matter which one is authoritative. We will assume that, as the detail-oriented scientist you are, you know that the start time is correct in the filename.

    We can assign a manual start time to our video files using the video_start_times block in the *Extraction Spec:*

        """),
        yaml_block("""
    rules:
      - interval_s: 10.0

    video_start_times:
      "EX2503_VID_20250411T202459Z_ROVHD_Low.mp4": "2025-04-11T20:24:59Z"
      "EX2503_VID_20250411T203000Z_ROVHD_Low.mp4": "2025-04-11T20:30:00Z"
      "EX2503_VID_20250411T203459Z_ROVHD_Low.mp4": "2025-04-11T20:34:59Z"

        """),
        mo.md("""
    If we run deep-framex with this input, it tells deep-framex to extract one frame every 10 seconds from each of the video files and sets their starting time appropriately. Let's write this YAML file the same as we have before.

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
                    "  - interval_s: 10.0\n"
                    "\n"
                    "video_start_times:\n"
                    "  \"EX2503_VID_20250411T202459Z_ROVHD_Low.mp4\": \"2025-04-11T20:24:59Z\"\n"
                    "  \"EX2503_VID_20250411T203000Z_ROVHD_Low.mp4\": \"2025-04-11T20:30:00Z\"\n"
                    "  \"EX2503_VID_20250411T203459Z_ROVHD_Low.mp4\": \"2025-04-11T20:34:59Z\""
                ),
                rows=10,
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
        contents = yaml.safe_load(form.value["text"])
        with open(form.value["filename"], "w", encoding="utf-8") as f:
            yaml.safe_dump(contents, f, sort_keys=False)
        mo.md(f"Saved to `{form.value["filename"]}`")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Something New!

    This extraction is running over multiple video files. We haven't run into this before. Here's what is happening behind the scenes when you click the Run Extraction button below:

    ```bash
    uv run deep-framex ./EX-clips/ --spec extraction_spec.yaml
    ```

    The download button placed our video clips in a directory called EX-clips. We don't have to specify the video files directly in this case, we can specify the directory where they are and deep-framex will perform the extraction we requested over all videos in the directory.

    This helps when you want to extract from multiple sequential videos. Constraints all still work the same as before - e.g., if you specify extraction intervals over a limited time period that doesn't cover all the video files, it won't extract over clips outside those times.
    """)


@app.cell
def _(mo):
    run_button = mo.ui.run_button(label="Run extraction")
    run_button
    return (run_button,)


@app.cell
def _(mo, run_button, shutil, subprocess):
    # Wait until the button is clicked before running anything.
    mo.stop(not run_button.value)

    # Clear any frames from a previous run so results don't mix together.
    # ignore_errors makes this a no-op when frames/ doesn't exist yet.
    shutil.rmtree("frames", ignore_errors=True)

    result = subprocess.run(
        ["uv", "run", "deep-framex", "./EX-clips/", "--spec", "extraction_spec.yaml"],
        capture_output=True,
        text=True,
        encoding="utf-8",
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
