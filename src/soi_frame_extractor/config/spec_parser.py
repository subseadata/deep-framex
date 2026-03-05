"""Extraction spec parser

Parses a YAML config file or dict into an ExtractionSpec.

Expected YAML shape:

    rules:
      - interval_s: 10.0
        periods:
          - start: "2024-01-15T10:00:00Z"
            end:   "2024-01-15T10:30:00Z"
        constraints:
          - column: depth
            min: 1000
            max: 1200
      - interval_s: 1.0
        # no periods key → rule applies to full session

    mappings:                  # omit entirely if no CSV was imported
      timestamp: utc_time      # required if mappings is present
      latitude:  lat           # optional
      longitude: lon           # optional
      depth:     z             # optional
      temp:      temperature_c # any extra columns are accepted

    metadata:                  # optional; all values stored as strings
      cruise_id: FK250101
      dive_id:   S0042
      vehicle:   SuBastian

    filename_template: "{dive_id}_{depth}m_T{utc}.jpg"  # optional
    xmp_namespace_uri:    https://example.org/myproject/ # optional
    xmp_namespace_prefix: myproj                         # optional

All datetimes must be ISO 8601 with explicit UTC offset (Z or +00:00).
"""

from pathlib import Path

from ..models.models import (
    ColumnMappings,
    ExtractionRule,
    ExtractionSpec,
    TimePeriod,
)


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
        ValueError: if any constraint is missing 'column' or has a
                    non-numeric min/max value.
        ValueError: if 'mappings' is present but 'timestamp' is missing.

    Optional top-level keys parsed into ExtractionSpec fields:
        filename_template:    str | None
        xmp_namespace_uri:    str | None  (model default if absent)
        xmp_namespace_prefix: str | None  (model default if absent)
        stream_output:        bool        (default False)
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
    #   constraints = []
    #   for each raw constraint dict in raw_rule.get('constraints', []):
    #     raise ValueError if 'column' is missing
    #     cast min and max to float if present; raise ValueError if not numeric
    #     append ExtractionRule.SensorConstraint(column=column, min=min, max=max)
    #
    #   append ExtractionRule(interval_s=interval_s, periods=periods, constraints=constraints)

    # mappings (optional)
    # if 'mappings' key is present:
    #   raise ValueError if 'timestamp' is missing from mappings
    #   build ColumnMappings(**raw['mappings']) — extra fields accepted as-is
    # else mappings = None

    # project_metadata (optional)
    # pass raw.get('metadata', {}) through as dict[str, str]

    # optional top-level fields (all have model defaults if absent)
    # filename_template    = raw.get('filename_template')           → str | None
    # xmp_namespace_uri    = raw.get('xmp_namespace_uri')           → str | None (use model default if absent)
    # xmp_namespace_prefix = raw.get('xmp_namespace_prefix')        → str | None (use model default if absent)

    # return ExtractionSpec(
    #     rules=rules,
    #     mappings=mappings,
    #     project_metadata=project_metadata,
    #     filename_template=filename_template,
    #     **({'xmp_namespace_uri': xmp_namespace_uri} if xmp_namespace_uri else {}),
    #     **({'xmp_namespace_prefix': xmp_namespace_prefix} if xmp_namespace_prefix else {}),
    # )
    pass
