"""
RawToIRMapper — orchestrates extraction from SectionChunks to SpecDocument.

For each chunk:
  1. SchemaRetriever.get_for_chunk() → mobilityhouse schema (RAG context)
  2. LLMExtractor.extract() → TestCase or ReusableState
  3. Assemble into SpecDocument

Failures on individual chunks are caught, logged, and recorded in
SpecDocument.failed_chunk_ids — they do not abort the full extraction.
"""
from __future__ import annotations

import logging
from typing import Any

from spec_to_test.adapters.base import BaseAdapter
from spec_to_test.extractors.base import SectionChunk
from spec_to_test.llm.extractor import LLMExtractor
from spec_to_test.llm.schema_retriever import SchemaRetriever
from spec_to_test.models.spec import SpecDocument
from spec_to_test.models.state import ReusableState, StateCondition
from spec_to_test.models.testcase import TestCase

logger = logging.getLogger(__name__)


class RawToIRMapper:
    """
    Converts a list of SectionChunks into a SpecDocument.

    Args:
        adapter:   Spec adapter (provides schema_map and metadata).
        extractor: LLMExtractor instance (injected for testability).
        retriever: SchemaRetriever instance (injected for testability).
    """

    def __init__(
        self,
        adapter: BaseAdapter,
        extractor: LLMExtractor,
        retriever: SchemaRetriever,
    ) -> None:
        self._adapter = adapter
        self._extractor = extractor
        self._retriever = retriever

    def map(self, chunks: list[SectionChunk]) -> SpecDocument:
        """
        Process *chunks* and return a fully populated SpecDocument.

        Test-case chunks are processed via LLMExtractor.
        Reusable-state chunks use lightweight rule-based extraction.
        """
        doc = SpecDocument(
            spec_id=f"{self._adapter.spec_id}-{self._adapter.spec_version}-part6",
            spec_version=self._adapter.spec_version,
            total_chunks_processed=len(chunks),
        )

        for chunk in chunks:
            try:
                if chunk["section_type"] == "testcase":
                    tc = self._extract_test_case(chunk)
                    doc.test_cases.append(tc)
                    if tc.low_confidence:
                        doc.low_confidence_count += 1

                elif chunk["section_type"] == "reusable_state":
                    rs = self._extract_reusable_state(chunk)
                    doc.reusable_states.append(rs)

            except Exception as exc:
                logger.error(
                    "Failed to extract chunk '%s': %s", chunk["id"], exc
                )
                doc.failed_chunk_ids.append(chunk["id"])

        logger.info(doc.summary())
        return doc

    # ------------------------------------------------------------------ #
    # Test case extraction (LLM-powered)                                  #
    # ------------------------------------------------------------------ #

    def _extract_test_case(self, chunk: SectionChunk) -> TestCase:
        schema = self._retriever.get_for_chunk(chunk["markdown"])
        return self._extractor.extract(chunk, schema)

    # ------------------------------------------------------------------ #
    # Reusable state extraction (rule-based — no LLM needed)              #
    # ------------------------------------------------------------------ #

    def _extract_reusable_state(self, chunk: SectionChunk) -> ReusableState:
        """
        Extract a ReusableState from a chunk using simple table parsing.

        No LLM call needed — reusable states have a consistent table structure.
        """
        conditions = self._parse_conditions_table(chunk["markdown"])
        return ReusableState(
            id=chunk["id"],
            title=chunk["title"],
            conditions=conditions,
            source_chunk_id=chunk["id"],
            page_start=chunk["page_start"],
            page_end=chunk["page_end"],
        )

    def _parse_conditions_table(self, markdown: str) -> list[StateCondition]:
        """Parse a Markdown table into StateCondition objects."""
        conditions: list[StateCondition] = []
        lines = markdown.splitlines()
        in_table = False
        header_seen = False

        for line in lines:
            stripped = line.strip()
            if not stripped.startswith("|"):
                in_table = False
                header_seen = False
                continue

            in_table = True
            # Skip separator row (| --- | --- |)
            if set(stripped.replace("|", "").replace("-", "").replace(" ", "")) == set():
                header_seen = True
                continue

            if not header_seen:
                header_seen = True  # This is the header row — skip it
                continue

            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) >= 2 and cells[0]:
                conditions.append(StateCondition(
                    condition=cells[0],
                    description=cells[1] if len(cells) > 1 else "",
                ))

        return conditions
