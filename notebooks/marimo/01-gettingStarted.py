import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium", css_file="theme-01.css")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Getting Started

    This notebook is here to confirm that you have a working environment for future notebooks. If this is your first time working with notebooks, a few key terms are defined below.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Markdown Cell

    This cell contains markdown text, usually to provide an explanation or instruction to the user.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Python Cell

    This cell is also a markdown cell, and it is here to tell you what the next cell will do.

    The following cell contains python code. If the notebook is running in app mode, you may not see any code.

    You can run the cell by pressing the arrow at the top of the cell or by clicking in the cell and pressing Ctrl+Enter. Try it now with the next cell. If you see an output block appear below the code text that says "hello world" then everything is working perfectly.
    """)
    return


@app.cell
def _():
    print("hello world") # this is the code cell, the output should appear below this line
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Requirements

    The next code block confirms the availability of the packages necessary for running deep-framex. This includes python packages named "av", "numpy", etc. The full list is in the code block below.

    Run it the same way as the cell we just ran. If you see a green "You're ready!" message, your environment is set up correctly. If the notebook is running in app mode, the cell might have already run and you will see the message.
    """)
    return


@app.cell
def _(mo):
    missing = []
    for pkg in ("deep_framex", "av", "numpy", "pydantic", "yaml", "PIL", "piexif"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        status = mo.callout(
            mo.md(
                f"""**Not ready yet.** These packages are missing: `{', '.join(missing)}`

    Please close this notebook and relaunch it from the repo folder with:

    ```
    uv run marimo edit notebooks/marimo/01-gettingStarted.py
    ```
    """
            ),
            kind="danger",
        )
    else:
        from importlib.metadata import version

        status = mo.callout(
            mo.md(
                f"**You're ready!** deep-framex {version('deep-framex')} and all dependencies are installed."
            ),
            kind="success",
        )
    status
    return


if __name__ == "__main__":
    app.run()
