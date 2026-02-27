"""Extraction spec parser

Parses a YAML config file or dict into an ExtractionSpec.

Expected YAML shape:

    rules:
      - interval_s: 10.0
        periods:
          - start: "2024-01-15T10:00:00Z"
            end:   "2024-01-15T10:30:00Z"
      - interval_s: 1.0
        # no periods key → rule applies to full session

All datetimes must be ISO 8601 with explicit UTC offset (Z or +00:00).
"""

from pathlib import Path

from ..models.models import ExtractionSpec, ExtractionRule, TimePeriod

# TODO evaluate how common other formats are and if they are compatible
# TODO unify this argument list in one location - duplicated in spec_parser
VIDEO_EXTENSIONS = {".mp4", ".mov"} # , ".avi", ".mkv", ".mts", ".m4v"}

def spec_from_file(path: Path) -> ExtractionSpec:
    """Parse a YAML config file into an ExtractionSpec.

    Args:
        path: path to a .yaml / .yml config file.

    Returns:
        Fully constructed ExtractionSpec.

    Raises:
        FileNotFoundError: if path does not exist.
        yaml.YAMLError: if the file is not valid YAML.
        ValueError: if the structure or field values are invalid.
    """
    # raise FileNotFoundError if path does not exist
    # open and yaml.safe_load the file
    # delegate to spec_from_dict
    pass


def spec_from_dict(raw: dict) -> ExtractionSpec:
    """Construct an ExtractionSpec from a parsed config dict.

    Args:
        raw: dict matching the expected YAML shape (see module docstring).

    Returns:
        Fully constructed ExtractionSpec.

    Raises:
        ValueError: if 'rules' key is missing or empty, if any rule is
                    missing 'interval_s', or if any datetime string is not
                    a valid ISO 8601 UTC timestamp.
    """
    # raise ValueError if 'rules' key is absent or the list is empty

    # for each raw rule dict in raw['rules']:
    #   raise ValueError if 'interval_s' is missing
    #   cast interval_s to float; raise ValueError if not a positive number
    #
    #   periods = []
    #   for each raw period dict in raw_rule.get('periods', []):
    #     parse 'start' and 'end' strings with datetime.fromisoformat
    #     raise ValueError if either string is missing or unparseable
    #     raise ValueError if the parsed datetime has no tzinfo (naive)
    #     raise ValueError if start >= end
    #     append TimePeriod(start=start, end=end)
    #
    #   append ExtractionRule(interval_s=interval_s, periods=periods)

    # return ExtractionSpec(rules=rules)
    pass
