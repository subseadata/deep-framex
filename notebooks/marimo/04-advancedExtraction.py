import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium", css_file="theme-04.css")


@app.cell
def _():
    import marimo as mo
    import subprocess
    import yaml

    return mo, subprocess, yaml


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Advanced extraction
    With a better understanding of the extractions and outputs, we're ready to try some more complicated extraction techniques.

    Let's start with varied intervals. We will use the same sample clip and `extraction_spec.yaml` file as before.

    Before we begin, take a moment and re-read the README section on **Extraction Spec**. Then briefly skim through the repository's full **Extraction Spec** file at [https://github.com/subseadata/deep-framex/blob/1f99c885621a9705e99e65d2d7ff4f6a6232c6c2/extraction_spec.yaml](https://github.com/subseadata/deep-framex/blob/1f99c885621a9705e99e65d2d7ff4f6a6232c6c2/extraction_spec.yaml).


    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Expanding our YAML file

    There's a lot of options in the full spec, but that's only for the sake of flexibility. You will probably not need to use them all at the same time, and it's much easier to approach by building slowly piece by piece.

    Recall our simple **Extraction Spec** from earlier:

    ```yaml
    rules:
        - interval_s: 10.0
    ```

    We are going to modify this file and add some more precise time constraints for frame extraction. To do this, we need to know what time the video starts so we can index appropriately.

    **Video file start time (UTC) must be known for deep-framex to work.** In our demo clip, the start time is encoded in the metadata: `2024-07-14T21:59:20Z`

    Let's modify `extraction_spec.yaml` below to extract one frame every 2 seconds from `T21:59:20` to `T21:59:26` and one frame every one second from `T21:59:28` to `T21:59:30`.

    Modify the spec to handle the 2 second interval extraction period as

    ```yaml
    rules:
        - interval_s: 2.0
          periods:
            - start: "2024-07-14T21:59:20Z"
              end: "2024-07-14T21:59:26Z"
    ```

    Knowing this, add the half second interval extraction period yourself.

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
            text=mo.ui.text_area(value="rules:\n  - interval_s: 2.0\n    periods:\n        - start: \"2024-07-14T21:59:20Z\"\n          end: \"2024-07-14T21:59:26Z\"", rows=10),
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

    To extract frames from it using the spec we just saved, we run a single command. If you're comfortable with it, open a terminal, navigate to the directory where we are running this notebook, and try to run this from your command line directly instead of using the button.

    ```
    uv run deep-framex clip.mp4 --spec extraction_spec.yaml
    ```

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
