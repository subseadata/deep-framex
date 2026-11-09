"""
Timestamp discovery

Parses timestamps from video filenames according to user-supplied configuration.
"""

import re
from datetime import datetime, timedelta


class ParseResult:
    def __init__(self, extracted="", parsed="", error=""):
        self.extracted = extracted
        self.parsed = parsed
        self.error = error


def validate_video_times_from_filename(config):
    if not isinstance(config, dict):
        raise ValueError(
            "Check the indentation in your spec file for 'video_times_from_filename'."
        )

    # Check for unknown keys
    all_keys = {"mode", "format", "offset", "separator", "group_number", "start_char", "end_char", "regex"}
    unknown_keys = config.keys() - all_keys
    if unknown_keys:
        raise ValueError(
            f"'video_times_from_filename' contains unknown keys: {sorted(unknown_keys)}"
        )

    required_keys = {
        "split": {"separator", "group_number"},
        "range": {"start_char", "end_char"},
        "regex": {"regex"},
    }

    # Common required options
    common_keys = {"mode", "format"}
    missing = common_keys - config.keys()
    if missing:
        raise ValueError(
            f"'video_times_from_filename' is missing required keys: {sorted(missing)}"
        )

    mode = config["mode"]

    if mode not in required_keys:
        raise ValueError(
            f"Invalid mode {mode!r}. Expected one of {list(required_keys)}"
        )

    # Mode-specific required options
    missing = required_keys[mode] - config.keys()
    if missing:
        raise ValueError(
            f"'video_times_from_filename' with mode {mode!r} is missing required keys: "
            f"{sorted(missing)}"
        )

    # Validate integer options
    int_keys = {"group_number", "start_char", "end_char"}
    for key in int_keys & config.keys():
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(
                f"'video_times_from_filename' option {key!r} must be an integer, got {value!r}"
            )


def parse_filename(
    filename: str,
    mode: str,
    format: str,
    offset: timedelta | None = None,
    separator: str = "",
    group_number: int = 0,
    start_char: int = 0,
    end_char: int = 1,
    regex: str = "",
):
    """
    Parse a timestamp from filename.

    Separator mode:
        filename.split(separator), group_number is 1-based.

    Range mode:
        filename[start_char:end_char], end is exclusive.

    Regex mode:
        re.search(regex, filename)

    The offset is applied after parsing.
    The resulting datetime is treated as UTC and written as such.
    """
    try:
        match mode:
            case "separator":
                if not separator:
                    return ParseResult(error="Separator cannot be empty.")

                parts = filename.split(separator)

                if group_number < 1 or group_number > len(parts):
                    return ParseResult(
                        error=f"Group {group_number} does not exist "
                            f"(filename has {len(parts)} groups)."
                    )

                extracted = parts[group_number - 1]

            case "range":
                if start_char < 1:
                    return ParseResult(error="Start character cannot be negative.")

                if end_char <= start_char:
                    return ParseResult(error="End character must be greater than start.")

                if start_char >= len(filename):
                    return ParseResult(error="Start character is outside the filename.")

                extracted = filename[(start_char - 1):end_char]

            case "regex":
                match = re.search(regex, filename)
                if not match:
                    return ParseResult(error="Regex did not match the filename.")
                extracted = match.group(1)


        if not extracted:
            return ParseResult(error="Extracted timestamp is empty.")

        try:
            parsed = datetime.strptime(extracted, format)
        except ValueError as exc:
            return ParseResult(
                extracted=extracted,
                error=f"Invalid timestamp: {exc}"
            )

        # The input is intentionally considered a naive timestamp.
        # The offset lets the user convert it to the desired UTC time.
        if offset:
            parsed += offset

        return ParseResult(extracted=extracted, parsed=parsed)

    except Exception as exc:
        return ParseResult(error=str(exc))