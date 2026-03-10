"""
OCPP-specific extraction helpers.

Supplements PdfExtractionPipeline with OCPP Part 6 quirks:
- TOC offset detection (cover + preface pages shift content page numbers)
- TC_ID normalisation (TC_B01_01 → canonical form)
"""
from __future__ import annotations

import re

_TOC_MARKER_RE = re.compile(r"Table of Contents", re.IGNORECASE)
_FIRST_SECTION_RE = re.compile(r"^#{1,2}\s+1[\. ]", re.MULTILINE)


def detect_toc_offset(markdown: str) -> int:
    """
    Estimate how many pages of front matter (cover, TOC) precede section 1.

    Returns the 0-based page index where section "1." first appears.
    This offset can be used to correct page numbers reported by pdfplumber.
    """
    toc_match = _TOC_MARKER_RE.search(markdown)
    section1_match = _FIRST_SECTION_RE.search(markdown)

    if not toc_match or not section1_match:
        return 0

    # Count page-break markers between start and section 1
    segment = markdown[: section1_match.start()]
    offset = segment.count("\n---\n")
    return offset


def normalise_tc_id(raw_id: str) -> str:
    """
    Normalise a raw TC identifier to canonical uppercase form.

    Examples:
        "tc_b01"      → "TC_B01"
        "TC-B01-01"   → "TC_B01_01"
    """
    return raw_id.upper().replace("-", "_")
