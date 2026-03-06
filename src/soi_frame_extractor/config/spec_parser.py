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

from datetime import datetime
from pathlib import Path

import yaml

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
    if not path.exists():
        raise FileNotFoundError(f"Spec file not found: {path}")
    with open(path) as f:
        raw = yaml.safe_load(f)
    return spec_from_dict(raw)


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
    if not raw.get('rules'):
        raise ValueError("'rules' key is missing or empty")

    rules = []
    for i, raw_rule in enumerate(raw['rules']):
        if 'interval_s' not in raw_rule:
            raise ValueError(f"Rule {i}: missing 'interval_s'")
        try:
            interval_s = float(raw_rule['interval_s'])
        except (TypeError, ValueError):
            raise ValueError(
                f"Rule {i}: 'interval_s' must be a positive number, got {raw_rule['interval_s']!r}"
            )
        if interval_s <= 0:
            raise ValueError(f"Rule {i}: 'interval_s' must be positive, got {interval_s}")

        periods = []
        for j, raw_period in enumerate(raw_rule.get('periods', [])):
            for key in ('start', 'end'):
                if key not in raw_period:
                    raise ValueError(f"Rule {i}, period {j}: missing '{key}'")
            try:
                start = datetime.fromisoformat(str(raw_period['start']))
                end = datetime.fromisoformat(str(raw_period['end']))
            except ValueError as e:
                raise ValueError(f"Rule {i}, period {j}: invalid datetime: {e}") from e
            if start.tzinfo is None or end.tzinfo is None:
                raise ValueError(
                    f"Rule {i}, period {j}: datetimes must be UTC-aware (use Z or +00:00)"
                )
            if start >= end:
                raise ValueError(f"Rule {i}, period {j}: start must be before end")
            periods.append(TimePeriod(start=start, end=end))

        constraints = []
        for k, raw_con in enumerate(raw_rule.get('constraints', [])):
            if 'column' not in raw_con:
                raise ValueError(f"Rule {i}, constraint {k}: missing 'column'")
            min_val = max_val = None
            for bound in ('min', 'max'):
                if raw_con.get(bound) is not None:
                    try:
                        val = float(raw_con[bound])
                    except (TypeError, ValueError):
                        raise ValueError(
                            f"Rule {i}, constraint {k}: '{bound}' must be numeric, "
                            f"got {raw_con[bound]!r}"
                        )
                    if bound == 'min':
                        min_val = val
                    else:
                        max_val = val
            constraints.append(
                ExtractionRule.SensorConstraint(
                    column=raw_con['column'], min=min_val, max=max_val
                )
            )

        rules.append(
            ExtractionRule(interval_s=interval_s, periods=periods, constraints=constraints)
        )

    # mappings (optional)
    mappings = None
    if 'mappings' in raw:
        if 'timestamp' not in raw['mappings']:
            raise ValueError("'mappings' block is present but 'timestamp' is missing")
        mappings = ColumnMappings(**raw['mappings'])

    # project_metadata (optional) — all values coerced to str
    project_metadata = {str(k): str(v) for k, v in raw.get('metadata', {}).items()}

    # interpolation_window — top-level, must be a positive integer
    raw_window = raw.get('interpolation_window', 2)
    try:
        interpolation_window = int(raw_window)
    except (TypeError, ValueError):
        raise ValueError(
            f"'interpolation_window' must be a positive integer, got {raw_window!r}"
        )
    if interpolation_window < 1:
        import warnings
        warnings.warn(
            f"'interpolation_window' must be at least 1 (got {interpolation_window}) — setting to 1.",
            UserWarning,
            stacklevel=2,
        )
        interpolation_window = 1

    # initial_offset_s — top-level, must be a non-negative number
    raw_offset = raw.get('initial_offset_s', 0.0)
    try:
        initial_offset_s = float(raw_offset)
    except (TypeError, ValueError):
        raise ValueError(
            f"'initial_offset_s' must be a non-negative number, got {raw_offset!r}"
        )
    if initial_offset_s < 0:
        raise ValueError(
            f"'initial_offset_s' must be non-negative, got {initial_offset_s}"
        )

    # max_workers — top-level, must be a positive integer
    raw_workers = raw.get('max_workers', 1)
    try:
        max_workers = int(raw_workers)
    except (TypeError, ValueError):
        raise ValueError(
            f"'max_workers' must be a positive integer, got {raw_workers!r}"
        )
    if max_workers < 1:
        raise ValueError(
            f"'max_workers' must be at least 1, got {max_workers}"
        )

    # optional top-level fields — only pass XMP overrides if explicitly set,
    # so the model defaults apply when the user omits them
    kwargs: dict = {}
    if xmp_uri := raw.get('xmp_namespace_uri'):
        kwargs['xmp_namespace_uri'] = xmp_uri
    if xmp_prefix := raw.get('xmp_namespace_prefix'):
        kwargs['xmp_namespace_prefix'] = xmp_prefix

    return ExtractionSpec(
        rules=rules,
        mappings=mappings,
        project_metadata=project_metadata,
        filename_template=raw.get('filename_template'),
        initial_offset_s=initial_offset_s,
        interpolation_window=interpolation_window,
        stream_output=bool(raw.get('stream_output', False)),
        max_workers=max_workers,
        **kwargs,
    )
