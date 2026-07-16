import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium", css_file="theme-05.css")


@app.cell
def _():
    import marimo as mo
    import subprocess
    import yaml
    import pandas as pd
    import matplotlib.pyplot as plt


    return mo, subprocess, yaml


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Sensor constrained extraction
    Now that we understand how to set up time-based extractions, we're ready to tackle sensor-based constraints. This is one of the most powerful features of deep-framex.

    Before we begin, take a moment and re-read the README section on **Extraction Spec**, and continue through **Sensor mappings**. You may notice some similarity to the time-based extractions.

    Briefly skim through the repository's full **Extraction Spec** file and focus on the two example sensor-based extraction section in [https://github.com/subseadata/deep-framex/blob/1f99c885621a9705e99e65d2d7ff4f6a6232c6c2/extraction_spec.yaml](https://github.com/subseadata/deep-framex/blob/1f99c885621a9705e99e65d2d7ff4f6a6232c6c2/extraction_spec.yaml).

    """)
    return

@app.cell(hide_code=True)
def _(mo):

    with open("sensor.csv") as c:
        csv_text = c.read()

    mo.md(f"""
    ## How do we handle sensor data?

    Sensor data is imported into deep-framex as comma-separated value (csv) files. Imported sensor data **must** have the following characteristics to be used by deep-framex:
    * Columns must be labeled
    * One column must include timestamps

    **Everything in deep-framex hinges on timestamps.**

    Here's a simple sensor data file as an example. It's already here in the notebook directory under `sensor.csv` if you want to open it in a text editor and take a look.

    ```csv
    {csv_text}
    ```

    We'll take a short look at the data plotted up for context.

    """)

@app.cell
def _(mo):
    df = pd.read_csv("sensor.csv")
    df["time"] = pd.to_datetime(df["time"])

    fig, ax1 = plt.subplots()

    ax1.plot(df["time"], df["depth_m"], color="steelblue", label="Depth")
    ax1.set_ylabel("Depth")
    ax1.tick_params(axis="y", labelcolor="steelblue")
    ax1.tick_params(axis="x", rotation=45)
    ax1.legend(loc="upper left")

    ax2 = ax1.twinx()
    ax2.plot(df["time"], df["temperature"], color="coral", label="Temperature")
    ax2.set_ylabel("Temperature (°C)")
    ax2.tick_params(axis="y", labelcolor="coral")
    ax2.legend(loc="upper right")

    fig.suptitle("Sensor readings over time")
    ax1.invert_yaxis()
    plt.tight_layout()

    fig


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Expanding our YAML file

    Recall our simple **Extraction Spec** from earlier:

    ```yaml
    rules:
      - interval_s: 10.0
    ```

    Let's modify `extraction_spec.yaml` below to extract one frame per second while the depth sensor reading is greater than 400m. This requires two additions to our YAML file.

    First are the extraction rules we want to apply to our video using the sensor data:

    ```yaml
    rules:
    - interval_s: 1.0
      constraints:
      - column: depth
        min: 400 
    ```

    The second is a mappings block that tells deep-framex what columns in our csv mean. Let's map our `time` and `depth_m` columns in our csv as:

    ```yaml
    mappings:
      timestamp:   time
      depth:       depth_m
    ```

    Our column name from the sensor file is on the right, and the names deep-framex uses are on the left. How did we know this? It's in the example `extraction_spec.yaml` and in the README on the repository.

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
            text=mo.ui.text_area(value="rules:\n  - interval_s: 1.0\n    constraints:\n    - column: depth\n      min: 400\nmappings:\n  timestamp: time\n  depth: depth_m", rows=10),
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

    To extract frames from it using the spec we just saved, we run a single command. Here again we have a button in the notebook, but if you were running this in a terminal environment you could use the following. **Notice the added flag for including sensor data.**

    ```bash
    uv run deep-framex clip.mp4 --spec extraction_spec.yaml --data sensor.csv
    ```

    Remember, in order to perform sensor-aware extractions, you must 
    1. Have timestamped csv sensor files
    2. Add a constriaints block and a sensor mappings block to your YAML file
    3. Call deep-framex with the --data flag and pass in the sensor file.

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
        ["rm", "-r", "frames/", "&&", "uv", "run", "deep-framex", "clip.mp4", "--spec", "extraction_spec.yaml", "--data", "sensor.csv"],
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
