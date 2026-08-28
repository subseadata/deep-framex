"""Extract time, longitude, and latitude from a GPGGA .RAW log.

Usage:
    uv run python gpgga_to_csv.py <input.RAW> <output.csv>

Each data row is a logger timestamp followed by a raw NMEA $GPGGA sentence.
The leading DATE column is MM/DD/YYYY despite the header naming it
YYYY/MM/DD; the logger date and time are used for the output timestamp
rather than the sentence's own FIX_TIME, which carries no date.

Latitude and longitude are NMEA ddmm.mmmm / dddmm.mmmm and are converted to
signed decimal degrees using the hemisphere columns.
"""

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path


def to_decimal(value: str, direction: str) -> float:
    """Convert an NMEA [d]ddmm.mmmm string plus hemisphere to decimal degrees."""
    degrees, minutes = divmod(float(value), 100.0)
    decimal = degrees + minutes / 60.0
    return -decimal if direction in ("S", "W") else decimal


def parse(path: Path):
    """Yield (timestamp, longitude, latitude) for each $GPGGA row in the file."""
    with path.open() as f:
        for line in f:
            if "$GPGGA" not in line:
                continue
            row = line.strip().split(",")
            timestamp = datetime.strptime(f"{row[0]} {row[1]}", "%m/%d/%Y %H:%M:%S.%f")
            yield timestamp, to_decimal(row[6], row[7]), to_decimal(row[4], row[5])


def main() -> None:
    source, destination = Path(sys.argv[1]), Path(sys.argv[2])
    with destination.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "longitude", "latitude"])
        for timestamp, lon, lat in parse(source):
            writer.writerow([
                timestamp.replace(tzinfo=timezone.utc).isoformat(),
                f"{lon:.6f}",
                f"{lat:.6f}",
            ])


if __name__ == "__main__":
    main()
