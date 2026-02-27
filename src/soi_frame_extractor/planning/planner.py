"""Extraction planner

Translates an ExtractionSpec and VideoSession into a list of VideoExtractionPlans —
one per video, each containing the offsets (seconds from t=0) to extract.
"""

from ..models.models import ExtractionSpec, VideoExtractionPlan, VideoSession


def plan(spec: ExtractionSpec, session: VideoSession) -> list[VideoExtractionPlan]:
    """Translate an ExtractionSpec into per-video extraction offsets.

    For each rule in the spec, generates all UTC timestamps that fall within
    the session by applying the rule's interval across its periods (or the full
    session if no periods are defined). Maps each UTC timestamp to the
    appropriate video in the session and converts it to a seconds-from-t=0
    offset. Deduplicates and sorts offsets within each video before returning.

    Args:
        spec (ExtractionSpec): one or more extraction rules defining intervals
                               and optional time periods.
        session (VideoSession): ordered list of probed VideoFiles covering the
                                dive.

    Returns:
        List of VideoExtractionPlan, one per video that has at least one frame
        to extract, ordered by video utc_start.

    Raises:
        ValueError: if a requested timestamp falls outside the span of the
                    session.
    """
    pass
