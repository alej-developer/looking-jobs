"""
parser.py — Regex-based job classification engine.

Classifies job offers by work modality (REMOTE, HYBRID, ON_SITE) and
geographic scope (SPAIN, INTERNATIONAL) using compiled regular
expressions with word-boundary anchors (\\b) for precision matching.
"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ─── Compiled Regex Patterns ────────────────────────────────────────────────
# Word-boundary anchors (\b) prevent false positives like "cremote" or "hybrids".

_REMOTE_PATTERN = re.compile(
    r"\b(?:remote|remoto|remota|teletrabajo|telecommute|work[\s-]?from[\s-]?home|wfh|"
    r"fully[\s-]?remote|100%[\s-]?remote|anywhere)\b",
    re.IGNORECASE,
)

_HYBRID_PATTERN = re.compile(
    r"\b(?:hybrid|híbrido|híbrida|semi[\s-]?presencial|flex[\s-]?office|"
    r"partial[\s-]?remote|mixed[\s-]?mode)\b",
    re.IGNORECASE,
)

_ON_SITE_PATTERN = re.compile(
    r"\b(?:on[\s-]?site|onsite|presencial|in[\s-]?office|office[\s-]?based|"
    r"in[\s-]?person)\b",
    re.IGNORECASE,
)

# ─── Geographic Scope Keywords ──────────────────────────────────────────────

_SPAIN_PATTERN = re.compile(
    r"\b(?:Madrid|Barcelona|Valencia|Sevilla|Seville|Bilbao|Málaga|Malaga|"
    r"Spain|España|ES\b)",
    re.IGNORECASE,
)

_INTERNATIONAL_PATTERN = re.compile(
    r"\b(?:Worldwide|Global|International|Anywhere|EMEA|Europe|EU[\s-]?wide|"
    r"All[\s-]?locations|No[\s-]?location[\s-]?restriction)\b",
    re.IGNORECASE,
)


# ─── Classification Result ──────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class JobClassification:
    """Immutable result of classifying a job offer."""

    work_modality: str    # REMOTE | HYBRID | ON_SITE | UNKNOWN
    geo_scope: str        # SPAIN | INTERNATIONAL | UNKNOWN
    modality_match: str   # The exact text fragment that triggered the modality match
    geo_match: str        # The exact text fragment that triggered the geo match


# ─── Public API ──────────────────────────────────────────────────────────────

def classify_job(title: str, url: str) -> JobClassification:
    """Classify a job offer by work modality and geographic scope.

    Analyzes both the job title and the URL to determine:
    1. **Work modality**: REMOTE, HYBRID, ON_SITE, or UNKNOWN.
    2. **Geographic scope**: SPAIN, INTERNATIONAL, or UNKNOWN.

    Priority order for modality (first match wins):
    ``REMOTE`` > ``HYBRID`` > ``ON_SITE`` > ``UNKNOWN``

    Args:
        title: The job posting title (e.g. "Senior Python Developer — Remote Spain").
        url: The full URL of the posting (may contain location slugs like
             ``/remote`` or ``/madrid``).

    Returns:
        A ``JobClassification`` dataclass with modality, geo scope,
        and the matched text fragments.
    """
    combined_text = f"{title} {url}"

    # ── Work modality classification (priority: REMOTE > HYBRID > ON_SITE) ──
    work_modality = "UNKNOWN"
    modality_match = ""

    remote_hit = _REMOTE_PATTERN.search(combined_text)
    if remote_hit:
        work_modality = "REMOTE"
        modality_match = remote_hit.group()
    else:
        hybrid_hit = _HYBRID_PATTERN.search(combined_text)
        if hybrid_hit:
            work_modality = "HYBRID"
            modality_match = hybrid_hit.group()
        else:
            onsite_hit = _ON_SITE_PATTERN.search(combined_text)
            if onsite_hit:
                work_modality = "ON_SITE"
                modality_match = onsite_hit.group()

    # ── Geographic scope classification ──────────────────────────────────────
    geo_scope = "UNKNOWN"
    geo_match = ""

    spain_hit = _SPAIN_PATTERN.search(combined_text)
    international_hit = _INTERNATIONAL_PATTERN.search(combined_text)

    if spain_hit and international_hit:
        # If both match, prioritize INTERNATIONAL (broader opportunity)
        geo_scope = "INTERNATIONAL"
        geo_match = international_hit.group()
    elif international_hit:
        geo_scope = "INTERNATIONAL"
        geo_match = international_hit.group()
    elif spain_hit:
        geo_scope = "SPAIN"
        geo_match = spain_hit.group()

    result = JobClassification(
        work_modality=work_modality,
        geo_scope=geo_scope,
        modality_match=modality_match,
        geo_match=geo_match,
    )

    logger.debug(
        "Classified job: title='%s' → modality=%s (matched='%s'), geo=%s (matched='%s')",
        title,
        result.work_modality,
        result.modality_match,
        result.geo_scope,
        result.geo_match,
    )

    return result
