import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium", css_file="theme-03.css")


@app.cell
def _():
    import marimo as mo
    import csv
    import json
    from pathlib import Path
    from PIL import Image, ExifTags

    return ExifTags, Image, Path, csv, json, mo


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Examine Output 

    With our frames successfull extracted, let's examine the output.

    If you were running locally, you would find these files in the directory where you ran deep-framex. In our notebook environment, we load them automatically from the `frames/` directory that was created during extraction.

    Below we will examine the frame metadata to understand what is output beyond the image.

    **Note that these metadata files accompanying our images are pretty sparse for now, because we haven't added any sensor data paired with our images.**

    """)
    return


@app.cell
def _(mo):
    # A refresh button whose value changes on each click. Any cell that reads
    # from frames/ references this, so clicking it re-runs those cells and
    # re-reads the directory — no page refresh needed.
    reload_button = mo.ui.refresh(label="🔄 Reload frames")
    mo.vstack([
        mo.md(
            "Just ran an extraction in another notebook (2, 4, or 5)? "
            "Click **Reload frames** to pull in the new output — "
            "no need to refresh the page."
        ),
        reload_button,
    ])
    return (reload_button,)


@app.cell
def _(Path, mo, reload_button):
    reload_button  # re-run this cell whenever the reload button is clicked

    frames_dir = Path("frames")
    images = sorted(
        p for p in frames_dir.glob("*") if p.suffix.lower() in {".jpg", ".jpeg"}
    )

    mo.stop(
        not images,
        mo.md("⚠️ No images found in `frames/`. Run an extraction first."),
    )

    preview = [mo.image(src=str(img), width=200) for img in images]

    # Flexible grid: up to 4 per row
    COLS = 4
    preview_rows = [
        mo.hstack(preview[i : i + COLS], justify="start")
        for i in range(0, len(preview), COLS)
    ]

    filename = mo.ui.dropdown(
        options={p.name: str(p) for p in images},
        value=images[0].name,
        label="Select image to render metadata below:",
    )
    mo.vstack([
        mo.md("## Preview images"),
        *preview_rows,
        mo.md("## Metadata"),
        filename,
        ])
    return (filename,)


@app.cell
def _(ExifTags, Image, filename, mo):
    mo.stop(not filename.value, mo.md("Select a frame above."))

    with Image.open(filename.value) as img:
        exif = img.getexif()

    # Pointer tags to the sub-IFDs — offsets, not real data.
    pointer_tags = {ExifTags.IFD.Exif, ExifTags.IFD.GPSInfo}

    # Top-level IFD0 tags (Make, Model, ...).
    exif_data = {
        ExifTags.TAGS.get(tag, tag): value
        for tag, value in exif.items()
        if tag not in pointer_tags
    }

    # DateTimeOriginal and friends live in the Exif sub-IFD.
    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    exif_data.update(
        {ExifTags.TAGS.get(tag, tag): value for tag, value in exif_ifd.items()}
    )

    # GPS coordinates / depth live in the GPS IFD.
    gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
    if gps_ifd:
        exif_data["GPS"] = {
            ExifTags.GPSTAGS.get(tag, tag): value for tag, value in gps_ifd.items()
        }

    mo.vstack([
        mo.md("""
        ### **EXIF metadata**

        Includes GPS timestamp and is embedded in each image.
        """),
        exif_data,
    ])
    return


@app.cell
def _(csv, mo, reload_button):
    reload_button  # re-run this cell whenever the reload button is clicked

    with open("frames/biigle_metadata.csv", newline="") as f:
        biigle_rows = list(csv.DictReader(f))

    mo.vstack([
        mo.md("""
        ### **BIIGLE metadata**
        Along with the frames we generate a BIIGLE-formatted metadata csv, which you can use to import metadata alongside your images in the BIIGLE interface. 
        """),
        mo.ui.table(biigle_rows, selection=None, show_search=False, show_download=False),
    ])
    return

@app.cell
def _(json, mo, reload_button):
    reload_button  # re-run this cell whenever the reload button is clicked

    with open("frames/ifdo.json", "r") as j:
        ifdo = json.load(j)

    mo.vstack([
        mo.md("""
        ### **IFDO metadata**
        The `ifdo.json` file holds metadata for all generated images following the IFDO specification in JSON structure.
        """),
        mo.json(ifdo, label="IFDO JSON metadata"),
    ])
    return


if __name__ == "__main__":
    app.run()
