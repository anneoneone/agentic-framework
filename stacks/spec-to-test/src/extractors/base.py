"""
BaseExtractor — abstract interface for PDF extraction implementations.

Produces a list of SectionChunk dicts, one per test case / reusable state.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, TypedDict

from spec_to_test.adapters.base import BaseAdapter


class SectionChunk(TypedDict):
    """
    One extracted section from the spec PDF.

    id            : stable identifier  (e.g. "TC_B01" or "RS_001")
    title         : full section heading text
    markdown      : extracted content as Markdown (tables preserved)
    page_start    : 1-based page number where section starts
    page_end      : 1-based page number where section ends (inclusive)
    section_type  : "testcase" | "reusable_state" | "unknown"
    """
    id: str
    title: str
    markdown: str
    page_start: int
    page_end: int
    section_type: Literal["testcase", "reusable_state", "unknown"]


class BaseExtractor(ABC):
    """Abstract extractor — subclasses handle PDF-library specifics."""

    @abstractmethod
    def extract(
        self,
        pdf_path: str,
        adapter: BaseAdapter,
    ) -> list[SectionChunk]:
        """
        Parse *pdf_path* and return one SectionChunk per detected section.

        Args:
            pdf_path: Absolute or relative path to the PDF file.
            adapter:  Spec adapter supplying section_patterns and helpers.

        Returns:
            List of SectionChunk dicts, ordered by page number.
        """
