import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import subprocess
    import yaml

    return mo, subprocess, yaml


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Our first extraction

    We'll start by reviewing the README and understanding critical inputs and outputs from deep-framex.

    Open the github repository at [https://github.com/subseadata/deep-framex/](https://github.com/subseadata/deep-framex/) and read the two sections on **Extraction Spec** and **Outputs**.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## What is a YAML file?

    The **Extraction Spec** is described as a YAML file. YAML files are structured text files that use indents, hyphens and other syntax to relate different pieces of information. We only need a text editor to create them, and we designate them as YAML files by saving them with the file extension `.yaml`

    Let's look at the simple YAML **Extraction Spec** below.

    ```yaml
    rules:
        - interval_s: 10.0
    ```

    That's it, that's the whole file.

    If we run deep-framex with this input, it tells deep-framex to extract one frame every 10 seconds from the whole video file (or all the videos in the extraction directory - more on that later).

    In the next cell, we can use a form to write and modify our **Extraction Spec** file, but you could also edit it in your favorite text editor.
    """)
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

    For this demo, there is already a video file named `clip.mp4` inside the notebook directory. To extract frames from it using the spec we just saved, we run a single command:

    ```
    uv run deep-framex clip.mp4 --spec extraction_spec.yaml
    ```

    That's the whole thing. It says: *run deep-framex on `clip.mp4`, using the rules in `extraction_spec.yaml`.*

    You could type that line into a terminal yourself. But you don't have to — press the button below and this notebook will run it for you.
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
