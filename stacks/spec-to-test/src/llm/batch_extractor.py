"""
BatchExtractor — submit all chunks to the Anthropic Message Batches API.

Cost: 50% of real-time API pricing (identical token count, half the cost).
Latency: asynchronous — results typically ready in minutes, up to 24h.
Accuracy: identical — uses same tool_use, prompt caching, schema RAG.

Workflow:
  1. submit(chunks, retriever) → writes batch_id to a state file, returns batch_id
  2. status(batch_id)          → "in_progress" | "ended"
  3. collect(batch_id)         → list[TestCase | None], saves to ExtractionCache

CLI usage:
  spec-to-test spec.pdf --batch           # submit and wait (polls every 30s)
  spec-to-test spec.pdf --batch --no-wait # submit only, print batch_id and exit
  spec-to-test --collect BATCH_ID         # collect previously submitted batch
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

from spec_to_test.adapters.base import BaseAdapter
from spec_to_test.extractors.base import SectionChunk
from spec_to_test.llm.extractor import (
    _EXTRACT_TOOL,
    _SYSTEM_PROMPT,
    _build_user_message,
    _trim_chunk,
    _trim_schema,
)
from spec_to_test.llm.extraction_cache import ExtractionCache
from spec_to_test.llm.schema_retriever import SchemaRetriever
from spec_to_test.models.testcase import TestCase

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 30
MAX_POLL_ATTEMPTS = 120  # 60 minutes max wait


class BatchExtractor:
    """
    Submits all test-case chunks to the Anthropic Batch API in one request.

    Args:
        client:    Anthropic sync client (anthropic.Anthropic()).
        model:     Model ID — must match the model used for real-time extraction
                   if mixing batch and non-batch results.
        cache:     ExtractionCache instance. Chunks with cached results are
                   skipped from the batch (free re-use of previous run).
        max_tokens: Per-request output token limit.
    """

    def __init__(
        self,
        client,
        model: str = "claude-sonnet-4-6",
        cache: Optional[ExtractionCache] = None,
        max_tokens: int = 1024,
    ) -> None:
        self._client = client
        self._model = model
        self._cache = cache
        self._max_tokens = max_tokens

    # ------------------------------------------------------------------ #
    # Submit                                                               #
    # ------------------------------------------------------------------ #

    def submit(
        self,
        chunks: list[SectionChunk],
        retriever: SchemaRetriever,
    ) -> str:
        """
        Submit all test-case chunks to the Batch API.

        Chunks already in the cache are skipped — their cached TestCase is
        used directly and they are NOT billed.

        Returns:
            batch_id (str) — use with status() and collect().
        """
        tc_chunks = [c for c in chunks if c["section_type"] == "testcase"]
        logger.info("Preparing batch for %d test-case chunks", len(tc_chunks))

        requests = []
        skipped = 0

        for chunk in tc_chunks:
            # Skip if cached
            if self._cache and self._cache.get(chunk["markdown"]) is not None:
                skipped += 1
                continue

            schema = retriever.get_for_chunk(chunk["markdown"])
            schema_props = _trim_schema(schema)
            trimmed_md = _trim_chunk(chunk["markdown"])

            requests.append({
                "custom_id": chunk["id"],
                "params": {
                    "model": self._model,
                    "max_tokens": self._max_tokens,
                    "system": [
                        {
                            "type": "text",
                            "text": _SYSTEM_PROMPT,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    "tools": [
                        {
                            **_EXTRACT_TOOL,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    "tool_choice": {"type": "tool", "name": "extract_test_case"},
                    "messages": [
                        {
                            "role": "user",
                            "content": _build_user_message(
                                chunk, trimmed_md, schema_props
                            ),
                        }
                    ],
                },
            })

        if not requests:
            logger.info("All %d chunks served from cache — no batch needed", skipped)
            return ""

        logger.info(
            "Submitting batch: %d requests (%d served from cache)",
            len(requests), skipped,
        )

        batch = self._client.beta.messages.batches.create(requests=requests)
        logger.info("Batch submitted: id=%s", batch.id)
        return batch.id

    # ------------------------------------------------------------------ #
    # Status                                                               #
    # ------------------------------------------------------------------ #

    def status(self, batch_id: str) -> str:
        """Return processing_status for a batch: 'in_progress' | 'ended'."""
        batch = self._client.beta.messages.batches.retrieve(batch_id)
        return batch.processing_status

    # ------------------------------------------------------------------ #
    # Collect                                                              #
    # ------------------------------------------------------------------ #

    def collect(
        self,
        batch_id: str,
        chunks: list[SectionChunk],
    ) -> tuple[list[TestCase], list[str]]:
        """
        Retrieve batch results and parse into TestCase objects.

        Also restores cached results for chunks that were skipped at submit time.

        Returns:
            (test_cases, failed_ids) — failed_ids lists chunk IDs that errored.
        """
        # Build a lookup: chunk_id → chunk (for cache fallback)
        chunk_map = {c["id"]: c for c in chunks if c["section_type"] == "testcase"}
        test_cases: list[TestCase] = []
        failed_ids: list[str] = []

        # First: restore cached entries (chunks skipped at submit time)
        if self._cache:
            for chunk in chunks:
                if chunk["section_type"] != "testcase":
                    continue
                cached = self._cache.get(chunk["markdown"])
                if cached is not None:
                    test_cases.append(cached)

        # Then: collect batch results
        if batch_id:
            for result in self._client.beta.messages.batches.results(batch_id):
                chunk_id = result.custom_id

                if result.result.type == "succeeded":
                    try:
                        tc = self._parse_result(result, chunk_map.get(chunk_id))
                        test_cases.append(tc)
                        # Cache successful non-low-confidence results
                        if self._cache and chunk_id in chunk_map:
                            self._cache.put(chunk_map[chunk_id]["markdown"], tc)
                    except Exception as exc:
                        logger.error("Parse error for %s: %s", chunk_id, exc)
                        failed_ids.append(chunk_id)

                elif result.result.type == "errored":
                    logger.error(
                        "Batch error for %s: %s",
                        chunk_id,
                        result.result.error,
                    )
                    failed_ids.append(chunk_id)

        logger.info(
            "Batch collect: %d test cases, %d failed",
            len(test_cases), len(failed_ids),
        )
        return test_cases, failed_ids

    # ------------------------------------------------------------------ #
    # Wait + collect (blocking)                                            #
    # ------------------------------------------------------------------ #

    def wait_and_collect(
        self,
        batch_id: str,
        chunks: list[SectionChunk],
    ) -> tuple[list[TestCase], list[str]]:
        """
        Poll until batch is complete, then collect results.

        Prints progress every POLL_INTERVAL_S seconds.
        """
        if not batch_id:
            return self.collect("", chunks)

        for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
            processing_status = self.status(batch_id)
            if processing_status == "ended":
                break

            batch = self._client.beta.messages.batches.retrieve(batch_id)
            counts = batch.request_counts
            logger.info(
                "Batch %s: in_progress (processed=%s/%s, attempt %d/%d)",
                batch_id[:16],
                counts.processing,
                counts.processing + counts.succeeded + counts.errored,
                attempt,
                MAX_POLL_ATTEMPTS,
            )
            time.sleep(POLL_INTERVAL_S)
        else:
            raise TimeoutError(
                f"Batch {batch_id} did not complete within "
                f"{MAX_POLL_ATTEMPTS * POLL_INTERVAL_S}s"
            )

        return self.collect(batch_id, chunks)

    # ------------------------------------------------------------------ #
    # Internal parsing                                                     #
    # ------------------------------------------------------------------ #

    def _parse_result(self, result, chunk: Optional[SectionChunk]) -> TestCase:
        """Parse a succeeded batch result into a TestCase."""
        message = result.result.message
        for block in message.content:
            if block.type == "tool_use" and block.name == "extract_test_case":
                tool_input = dict(block.input)
                if chunk:
                    tool_input.setdefault("id", chunk["id"])
                    tool_input.setdefault("title", chunk["title"])
                    tool_input["source_chunk_id"] = chunk["id"]
                    tool_input["page_start"] = chunk["page_start"]
                    tool_input["page_end"] = chunk["page_end"]
                tool_input.setdefault("low_confidence", False)
                return TestCase.model_validate(tool_input)
        raise ValueError(f"No tool_use block in batch result for {result.custom_id}")
