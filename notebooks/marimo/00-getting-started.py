import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium", css_file="theme-00.css")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Getting Started

    This notebook is here to confirm that you have a working environment for future notebooks. If you see a green "You're ready!" message, your environment is set up correctly. 
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
