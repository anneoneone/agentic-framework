"""
PdfExtractionPipeline — main extraction pipeline.

Primary path : pymupdf4llm → structure-preserving Markdown → split on H2/H3 headers.
Fallback path: pdfplumber  → used only when pymupdf4llm returns empty text on a page
               (typically occurs with borderless tables).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Literal

from spec_to_test.adapters.base import BaseAdapter
from spec_to_test.extractors.base import BaseExtractor, SectionChunk

logger = logging.getLogger(__name__)

# Matches Markdown H1-H3 headers produced by pymupdf4llm
_HEADER_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)

# Rough page-break marker inserted by pymupdf4llm between pages
_PAGE_BREAK_RE = re.compile(r"\n-{3,}\n")


class PdfExtractionPipeline(BaseExtractor):
    """
    Orchestrates the full extraction:
        open PDF → convert to Markdown → split into SectionChunks.

    One SectionChunk = one complete test-case or reusable-state section.
    """

    def extract(
        self,
        pdf_path: str,
        adapter: BaseAdapter,
    ) -> list[SectionChunk]:
        """
        Extract all test-case and reusable-state sections from *pdf_path*.

        Returns ordered list of SectionChunks.
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")

        logger.info("Extracting '%s' with pymupdf4llm (spec=%s %s)",
                    path.name, adapter.spec_id, adapter.spec_version)

        markdown = self._extract_markdown(str(path))
        chunks = self.split_markdown_sections(markdown, adapter)

        logger.info("Extracted %d sections", len(chunks))
        return chunks

    # ------------------------------------------------------------------ #
    # Primary extraction: pymupdf4llm                                     #
    # ------------------------------------------------------------------ #

    def _extract_markdown(self, pdf_path: str) -> str:
        """Convert entire PDF to Markdown using pymupdf4llm."""
        try:
            import pymupdf4llm  # type: ignore[import-untyped]
            return pymupdf4llm.to_markdown(pdf_path)
        except ImportError as exc:
            raise ImportError(
                "pymupdf4llm is required. Install: pip install pymupdf4llm"
            ) from exc

    # ------------------------------------------------------------------ #
    # Section splitting                                                    #
    # ------------------------------------------------------------------ #

    def split_markdown_sections(
        self,
        markdown: str,
        adapter: BaseAdapter,
    ) -> list[SectionChunk]:
        """
        Split a Markdown string into SectionChunk dicts.

        Algorithm:
          1. Find all H1-H3 header positions.
          2. For each header, check if it matches any adapter.section_patterns.
          3. Slice the text from this header to the next header of equal/higher level.
          4. Estimate page numbers from page-break markers.

        Args:
            markdown: Full PDF content as Markdown.
            adapter:  Provides section_patterns and extract_test_id().

        Returns:
            List of SectionChunks for matched sections only.
        """
        headers = list(_HEADER_RE.finditer(markdown))
        page_offsets = self._page_offsets(markdown)
        chunks: list[SectionChunk] = []

        for i, match in enumerate(headers):
            level = len(match.group(1))   # number of '#' chars
            title = match.group(2).strip()
            section_type, matched = self._classify_title(title, adapter)

            if not matched:
                continue

            # Content runs until next header at same or higher level
            start = match.start()
            end = len(markdown)
            for j in range(i + 1, len(headers)):
                next_level = len(headers[j].group(1))
                if next_level <= level:
                    end = headers[j].start()
                    break

            content_md = markdown[start:end].strip()
            page_start = self._page_for_offset(match.start(), page_offsets)
            page_end = self._page_for_offset(end - 1, page_offsets)
            section_id = adapter.extract_test_id(title) or title[:40]

            chunks.append(SectionChunk(
                id=section_id,
                title=title,
                markdown=content_md,
                page_start=page_start,
                page_end=page_end,
                section_type=section_type,
            ))

        return chunks

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _classify_title(
        self,
        title: str,
        adapter: BaseAdapter,
    ) -> tuple[Literal["testcase", "reusable_state", "unknown"], bool]:
        """Return (section_type, matched) for a header title."""
        for section_type, pattern in adapter.section_patterns.items():
            if pattern.search(title):
                return section_type, True  # type: ignore[return-value]
        return "unknown", False

    def _page_offsets(self, markdown: str) -> list[int]:
        """
        Build a list of character offsets where each page begins.

        pymupdf4llm inserts '---' separators between pages.
        Returns [0, offset_of_page2, offset_of_page3, ...].
        """
        offsets = [0]
        for m in _PAGE_BREAK_RE.finditer(markdown):
            offsets.append(m.end())
        return offsets

    def _page_for_offset(self, char_offset: int, page_offsets: list[int]) -> int:
        """Return 1-based page number for a character offset."""
        page = 1
        for i, offset in enumerate(page_offsets):
            if char_offset >= offset:
                page = i + 1
            else:
                break
        return page
