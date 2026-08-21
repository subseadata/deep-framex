"""Convert a Sea-Bird .cnv CTD cast to a deep-framex sensor CSV.

Usage:
    uv run python cnv_to_csv.py <input.cnv> <output.csv>

The .cnv timestamp column (timeQ) is "Time, NMEA [seconds]" — seconds since
2000-01-01 00:00:00 UTC, in whole seconds only.  The epoch is confirmed
against the file's own header: the first data row's timeQ must equal the
'# start_time = ...' line, and the script fails if it doesn't.

The instrument scans at 24 Hz, so ~24 rows share each one-second stamp.
deep-framex stores sensor readings with the timestamp as a PRIMARY KEY, so
duplicate stamps cannot be imported.  Rows are therefore averaged into one
reading per second, which also smooths the per-scan noise.

Dropped columns: prDE (the same pressure as prDM, in psi) and modError/flag
(bookkeeping, constant zero in this cast).
"""

import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# timeQ is seconds since this instant, not the Unix epoch.
NMEA_EPOCH = datetime(2000, 1, 1, tzinfo=timezone.utc)

# Source column name -> (output name, decimal places), by position in the .cnv row.
# Positions are verified against the '# name N =' header lines before use.
COLUMNS = {
    "prDM": ("pressure_dbar", 3),
    "t090C": ("temperature_c", 4),
    "c0S/m": ("conductivity_sm", 6),
    "seaTurbMtr": ("turbidity_ftu", 3),
    "sbeox0V": ("oxygen_raw_v", 4),
    "upoly0": ("orp", 5),
}


def parse_header(path: Path) -> tuple[list[str], datetime, int]:
    """Read the .cnv header.

    Returns:
        (column names in row order, start_time from the header, line number of *END*).
    """
    names: dict[int, str] = {}
    start_time = None
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            if line.startswith("*END*"):
                break
            if m := re.match(r"# name (\d+) = ([^:]+):", line):
                names[int(m.group(1))] = m.group(2).strip()
            elif m := re.match(r"# start_time = (.+?)\s*\[", line):
                start_time = datetime.strptime(
                    m.group(1).strip(), "%b %d %Y %H:%M:%S"
                ).replace(tzinfo=timezone.utc)
    return [names[i] for i in sorted(names)], start_time, lineno


def convert(src: Path, dst: Path) -> None:
    names, start_time, header_end = parse_header(src)

    time_col = names.index("timeQ")
    wanted = {names.index(k): v for k, v in COLUMNS.items()}

    # Sum and count per second so the mean can be taken in one pass.
    sums: dict[int, list[float]] = defaultdict(lambda: [0.0] * len(wanted))
    counts: dict[int, int] = defaultdict(int)
    dropped = 0
    first_t = None

    with open(src) as f:
        for _ in range(header_end):
            next(f)
        for line in f:
            parts = line.split()
            if not parts:
                continue
            t = int(parts[time_col])
            if first_t is None:
                first_t = t
            # A momentary NMEA dropout stamps a row with midnight, which would
            # place its readings hours away from where they belong.
            if t < first_t:
                dropped += 1
                continue
            bucket = sums[t]
            for slot, idx in enumerate(wanted):
                bucket[slot] += float(parts[idx])
            counts[t] += 1

    # The header states when the first scan was taken; if our epoch assumption is
    # wrong, this is where it shows up rather than in silently shifted output.
    derived = NMEA_EPOCH + timedelta(seconds=first_t)
    if derived != start_time:
        raise SystemExit(
            f"Epoch check failed: first row timeQ={first_t} gives {derived.isoformat()}, "
            f"but the header's start_time is {start_time.isoformat()}."
        )

    out_names = [v[0] for v in wanted.values()]
    places = [v[1] for v in wanted.values()]

    with open(dst, "w") as out:
        out.write("utc_time," + ",".join(out_names) + "\n")
        for t in sorted(sums):
            n = counts[t]
            utc = NMEA_EPOCH + timedelta(seconds=t)
            values = ",".join(
                f"{sums[t][i] / n:.{places[i]}f}" for i in range(len(out_names))
            )
            out.write(f"{utc.strftime('%Y-%m-%dT%H:%M:%SZ')},{values}\n")

    print(f"{dst}: {len(sums)} rows (one per second), {sum(counts.values())} scans averaged")
    print(f"  {derived.isoformat()} -> {(NMEA_EPOCH + timedelta(seconds=max(sums))).isoformat()}")
    if dropped:
        print(f"  dropped {dropped} row(s) with an out-of-range NMEA stamp")


if __name__ == "__main__":
    convert(Path(sys.argv[1]), Path(sys.argv[2]))
