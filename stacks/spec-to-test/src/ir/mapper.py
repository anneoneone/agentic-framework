"""
RawToIRMapper — orchestrates extraction from SectionChunks to SpecDocument.

Two execution modes:
  map()       — synchronous, sequential (simple, for small specs or testing)
  map_async() — async, parallel (recommended for 400+ test case specs)

For each chunk:
  1. SchemaRetriever.get_for_chunk() → mobilityhouse schema (RAG context)
  2. LLMExtractor.extract() → TestCase  (LLM, one call per TC)
     LLMExtractor rule-based → ReusableState (no LLM)
  3. Assemble into SpecDocument

Failures on individual chunks are caught, logged, and recorded in
SpecDocument.failed_chunk_ids — they never abort the full extraction.
"""
from __future__ import annotations

import asyncio
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

# Max concurrent LLM calls. Anthropic rate limit is 2000 RPM for Sonnet;
# 50 concurrent is safe and ~50x faster than sequential.
_MAX_CONCURRENCY = 50


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

    # ------------------------------------------------------------------ #
    # Sync map (sequential) — kept for backward compat + small specs      #
    # ------------------------------------------------------------------ #

    def map(self, chunks: list[SectionChunk]) -> SpecDocument:
        """
        Process *chunks* sequentially and return a SpecDocument.

        For 400+ test cases, prefer map_async() which is ~50x faster.
        """
        doc = self._empty_doc(len(chunks))
        for chunk in chunks:
            self._process_chunk_into(chunk, doc)
        logger.info(doc.summary())
        return doc

    # ------------------------------------------------------------------ #
    # Async map (parallel) — recommended for production use               #
    # ------------------------------------------------------------------ #

    async def map_async(self, chunks: list[SectionChunk]) -> SpecDocument:
        """
        Process *chunks* in parallel using asyncio.gather().

        Requires an AsyncAnthropic client in LLMExtractor.
        Respects _MAX_CONCURRENCY to stay within API rate limits.

        Usage from sync code:
            doc = asyncio.run(mapper.map_async(chunks))
        """
        doc = self._empty_doc(len(chunks))
        semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)

        async def bounded(chunk: SectionChunk) -> None:
            async with semaphore:
                await self._process_chunk_into_async(chunk, doc)

        await asyncio.gather(*[bounded(c) for c in chunks])
        logger.info(doc.summary())
        return doc

    # ------------------------------------------------------------------ #
    # Chunk processing — sync                                             #
    # ------------------------------------------------------------------ #

    def _process_chunk_into(self, chunk: SectionChunk, doc: SpecDocument) -> None:
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
            logger.error("Failed to extract chunk '%s': %s", chunk["id"], exc)
            doc.failed_chunk_ids.append(chunk["id"])

    # ------------------------------------------------------------------ #
    # Chunk processing — async                                            #
    # ------------------------------------------------------------------ #

    async def _process_chunk_into_async(
        self, chunk: SectionChunk, doc: SpecDocument
    ) -> None:
        try:
            if chunk["section_type"] == "testcase":
                schema = self._retriever.get_for_chunk(chunk["markdown"])
                tc = await self._extractor.extract_async(chunk, schema)
                # Thread-safety: list.append is GIL-safe in CPython
                doc.test_cases.append(tc)
                if tc.low_confidence:
                    doc.low_confidence_count += 1
            elif chunk["section_type"] == "reusable_state":
                rs = self._extract_reusable_state(chunk)
                doc.reusable_states.append(rs)
        except Exception as exc:
            logger.error("Failed async extract '%s': %s", chunk["id"], exc)
            doc.failed_chunk_ids.append(chunk["id"])

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
        conditions: list[StateCondition] = []
        header_seen = False

        for line in markdown.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|"):
                header_seen = False
                continue
            # Skip separator row
            if not stripped.replace("|", "").replace("-", "").replace(" ", ""):
                header_seen = True
                continue
            if not header_seen:
                header_seen = True
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) >= 2 and cells[0]:
                conditions.append(StateCondition(
                    condition=cells[0],
                    description=cells[1] if len(cells) > 1 else "",
                ))

        return conditions

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _empty_doc(self, total_chunks: int) -> SpecDocument:
        return SpecDocument(
            spec_id=f"{self._adapter.spec_id}-{self._adapter.spec_version}-part6",
            spec_version=self._adapter.spec_version,
            total_chunks_processed=total_chunks,
        )


# ------------------------------------------------------------------ #
# Knowledge step — runs AFTER extraction, BEFORE code generation      #
# ------------------------------------------------------------------ #

def save_knowledge(
    chunks: list[SectionChunk],
    knowledge_dir: str,
    stack: str = "spec-to-test",
    pdf_path: str = "",
) -> None:
    """
    Build the local vector index and write spec learnings to the Memento graph.

    This is the 'save-knowledge' pipeline step, inserted between IR mapping
    and code generation. It is idempotent — re-running only indexes new chunks.

    Args:
        chunks:        All SectionChunks from PdfExtractionPipeline.extract().
        knowledge_dir: Directory to persist the vector index.
        stack:         Memento stack name for Learning nodes.
        pdf_path:      Source PDF path (stored in index metadata only).
    """
    from spec_to_test.knowledge.indexer import SpecKnowledgeIndex
    from spec_to_test.knowledge.memento_bridge import MementoBridge

    # 1. Local vector index (always runs — no external dependency)
    index = SpecKnowledgeIndex(knowledge_dir)
    index.build(chunks, pdf_path=pdf_path)

    # 2. Memento graph (gracefully skipped when MCP server is unavailable)
    bridge = MementoBridge(stack=stack)
    written = bridge.index_chunks(chunks)
    if written:
        logger.info("Memento: %d Learning nodes written to graph", written)
