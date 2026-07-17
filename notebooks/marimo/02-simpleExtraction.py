import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium", css_file="theme-02.css")


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
def _(mo):
    mo.md("""
    # Our first extraction

    We'll start by reviewing the README and understanding critical inputs and outputs from deep-framex.

    Open the github repository at [https://github.com/subseadata/deep-framex/](https://github.com/subseadata/deep-framex/) and read the two sections on **Extraction Spec** and **Outputs**.
    """)
    return


@app.cell(hide_code=True)
def _(mo, yaml_block):
    mo.vstack([
        mo.md("""
    ## What is a YAML file?

    The **Extraction Spec** is described as a YAML file. YAML files are structured text files that use indents, hyphens and other syntax to relate different pieces of information. We only need a text editor to create them, and we designate them as YAML files by saving them with the file extension `.yaml`

    Let's look at the simple YAML **Extraction Spec** below.
        """),
        yaml_block("""
    rules:
      - interval_s: 10.0
        """),
        mo.md("""
    That's it, that's the whole file.

    If we run deep-framex with this input, it tells deep-framex to extract one frame every 10 seconds from the whole video file (or all the videos in the extraction directory - more on that later).

    In the next cell, we can use a form to write and modify our **Extraction Spec** file. If you were working in your local terminal environment, you can edit YAML files in any text editor.

    Confirm the YAML file below and press `Submit` to save the file to `extraction_spec.yaml` in our current working directory.
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
            text=mo.ui.text_area(value="rules:\n    - interval_s: 10.0", rows=10),
            filename=mo.ui.text(value="extraction_spec.yaml"),
        )
        .form(validate=check_yaml)
    )
    form
    return (form,)


@app.cell
def _(form, mo):
    if form.value:
        contents = yaml.safe_load(form.value["text"])
        with open(form.value["filename"], "w") as f:
            yaml.safe_dump(contents, f, sort_keys=False)
        mo.md(f"Saved to `{form.value["filename"]}`")
    return

@app.cell
def _(mo):
    mo.md("""
    ## Running the Extraction

    Great! Now that we have a valid YAML spec file, we can run extraction on a video file.

    For this demo, there is already a video file named `clip.mp4` inside the notebook directory. To extract frames from it using the spec we just saved, we would run a single command in our local terminal:

    ```
    uv run deep-framex clip.mp4 --spec extraction_spec.yaml
    ```

    That's the whole thing. It says: *run deep-framex on `clip.mp4`, using the rules in `extraction_spec.yaml`.*

    You could type that line into a terminal yourself. But you don't have to — press the button below and this notebook will run it for you here in the notebook directory.
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
        ["uv", "run", "deep-framex", "clip.mp4", "--spec", "extraction_spec.yaml"],
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
