import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium", css_file="theme-05.css")


@app.cell
def _():
    import marimo as mo
    import subprocess
    import yaml
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

    return mo, subprocess, yaml, yaml_block


@app.cell(hide_code=True)
def _(mo, yaml_block):
    mo.vstack([
        mo.md("""
    # Review
    Let's review what we have learned so far.

    ## Ins and Outs
    - deep-framex is minimally called as

    `deep-framex {SOURCE} --spec {SPEC}`

    where SOURCE is the video file source and SPEC is the extraction spec file

    ## Extraction Spec
    - YAML files (just a text file with structured formatting)
    - INPUT to deep-framex
    - Contain constraints that tell deep-framex what to extract, and when
    - Can combine different rules and mappings to handle time-based or sensor-based extractions

    ## Rules
    - Written in our YAML **extraction spec**
    - Define *when* frames are extracted -- recall that everything depends on timestamps
    - Always contain **intervals**
    - *May* contain **periods** and **constraints**

    ### Interval
    - Answers the question *how frequently should a frame be extracted?*
    - Unit is *seconds*
    - Without a *period* defined, intervals are applied to whole video or all videos in the directory
        """),
        yaml_block("""
    rules:
      - interval_s: 10.0
        """),
        mo.md("""
    ### Period
    - Answers the question *during which times are we extracting frames?*
    - Always in UTC format: `yyyy-mm-ddThh:mm:ssZ`
    - Requires a *start* and an *end*
        """),
        yaml_block("""
    rules:
      - interval_s: 20
        periods:
          - start: "2025-11-02T10:20:00Z"
            end: "2025-11-02T10:30:00Z"
        """),
        mo.md("""
    ### Constraints
    - Used to constrain extractions with sensor data
    - Requires
      - Sensor csv passed as input with the `--data` flag:
      `deep-framex {SOURCE} --spec {SPEC} --data {SENSOR}`
      - **constraint** block in the **rules** section of our **extraction spec** YAML file with our csv column and the min OR max OR both of the value:
        """),
        yaml_block("""
    rules:
      - interval_s: 5.0
        constraints:
        - column: temperature
          min: 1.8
          max: 2.2
        """),
        mo.md("""
      - **mappings** block in the **extraction spec** that tells deep-framex what our csv columns map to
        """),
        yaml_block("""
    mappings:
      timestamp: time
      temperature: temp_C
        """),
        mo.md("""
      - **and as always, timestamps are required in our sensor data**
        """),
    ])
    return

if __name__ == "__main__":
    app.run()
