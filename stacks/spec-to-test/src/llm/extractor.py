"""
LLMExtractor — single-call test-case extraction via Anthropic Messages API.

Optimizations vs. the two-step design:
  1. MERGED classify+extract  — test_type is a required tool field, eliminating
     a separate API call per test case (~422 saved calls for OCPP 2.0.1).
  2. Prompt caching           — system prompt and tool definition are marked with
     cache_control=ephemeral; cached tokens cost 10% of uncached input tokens.
  3. Schema RAG truncation    — only the `properties` section of the mobilityhouse
     schema is injected (not $defs / boilerplate), reducing schema tokens ~50%.
  4. Chunk trimming           — decorative page breaks and whitespace stripped
     before sending, reducing chunk tokens ~10-15%.

Retries up to MAX_RETRIES times on Pydantic ValidationError.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from pydantic import ValidationError

from spec_to_test.extractors.base import SectionChunk
from spec_to_test.models.testcase import Direction, TestCase, TestType

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

# ------------------------------------------------------------------ #
# Lean tool schema — no verbose descriptions (saves input tokens)     #
# ------------------------------------------------------------------ #

_EXTRACT_TOOL = {
    "name": "extract_test_case",
    "description": "Extract structured TestCase from spec section. Use exact values from text.",
    "input_schema": {
        "type": "object",
        "properties": {
            "id":    {"type": "string"},
            "title": {"type": "string"},
            "test_type": {
                "type": "string",
                "enum": [t.value for t in TestType],
            },
            "preconditions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description":        {"type": "string"},
                        "reusable_state_ref": {"type": "string"},
                    },
                    "required": ["description"],
                },
            },
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "step_number":  {"type": "integer"},
                        "description":  {"type": "string"},
                        "action":       {"type": "string"},
                        "message_type": {"type": "string"},
                        "direction": {
                            "type": "string",
                            "enum": [d.value for d in Direction],
                        },
                        "assertions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "description":    {"type": "string"},
                                    "field_path":     {"type": "string"},
                                    "expected_value": {"type": "string"},
                                    "operator":       {"type": "string"},
                                },
                                "required": ["description"],
                            },
                        },
                    },
                    "required": ["step_number", "description", "action"],
                },
            },
            "expected_outcome": {"type": "string"},
        },
        "required": ["id", "title", "test_type", "steps"],
    },
}

# System prompt — constant, gets cached after first call
_SYSTEM_PROMPT = (
    "You are an expert OCPP 2.0.1 test specification parser. "
    "Extract every step, precondition, and assertion verbatim from the spec section. "
    "Do NOT invent values. Use exact field names from the OCPP schema. "
    "test_type must be one of: "
    + ", ".join(t.value for t in TestType)
    + "."
)

# Regex to strip pymupdf4llm page-break decorators from chunk content
_PAGE_BREAK_RE = re.compile(r"\n-{3,}\n")
_WHITESPACE_RE = re.compile(r"\n{3,}")


class LLMExtractor:
    """
    Extracts a TestCase from a SectionChunk in a single LLM call.

    Optimized for minimum token cost while preserving extraction accuracy:
    - System prompt cached via Anthropic prompt caching
    - Tool definition cached (constant across all calls)
    - Schema injected as trimmed `properties` block only
    - Chunk Markdown trimmed before sending

    Args:
        client:     Anthropic client instance (sync or async).
        model:      Model ID (default: claude-sonnet-4-6).
        max_tokens: Max output tokens (keep low — tool_use output is compact).
    """

    def __init__(
        self,
        client: Any,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 1024,
    ) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def extract(
        self,
        chunk: SectionChunk,
        schema_context: dict,
    ) -> TestCase:
        """
        Extract a TestCase from *chunk* in a single API call.

        Args:
            chunk:          SectionChunk from the PDF extractor.
            schema_context: Full mobilityhouse schema dict. Will be trimmed
                            internally to `properties` only.

        Returns:
            Parsed TestCase Pydantic model.

        Raises:
            RuntimeError: If all retries are exhausted.
        """
        schema_props = _trim_schema(schema_context)
        trimmed_md = _trim_chunk(chunk["markdown"])

        last_error: Optional[Exception] = None
        low_confidence = False

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    system=[
                        {
                            "type": "text",
                            "text": _SYSTEM_PROMPT,
                            # Cached — same for every call in this session
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    tools=[
                        {
                            **_EXTRACT_TOOL,
                            # Cache tool definition — constant across all calls
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    tool_choice={"type": "tool", "name": "extract_test_case"},
                    messages=[
                        {
                            "role": "user",
                            "content": _build_user_message(
                                chunk, trimmed_md, schema_props
                            ),
                        }
                    ],
                )

                tool_input = self._parse_tool_response(response)
                tool_input.setdefault("id", chunk["id"])
                tool_input.setdefault("title", chunk["title"])
                tool_input["source_chunk_id"] = chunk["id"]
                tool_input["page_start"] = chunk["page_start"]
                tool_input["page_end"] = chunk["page_end"]
                tool_input["low_confidence"] = low_confidence

                return TestCase.model_validate(tool_input)

            except (ValidationError, KeyError, ValueError) as exc:
                last_error = exc
                low_confidence = True
                logger.warning(
                    "Extraction attempt %d/%d failed for '%s': %s",
                    attempt, MAX_RETRIES, chunk["id"], exc,
                )

        raise RuntimeError(
            f"LLM extraction failed for chunk '{chunk['id']}' "
            f"after {MAX_RETRIES} attempts: {last_error}"
        )

    async def extract_async(
        self,
        chunk: SectionChunk,
        schema_context: dict,
    ) -> TestCase:
        """
        Async variant for parallel processing via RawToIRMapper.map_async().

        Requires an AsyncAnthropic client to be passed at construction time.
        """
        schema_props = _trim_schema(schema_context)
        trimmed_md = _trim_chunk(chunk["markdown"])

        last_error: Optional[Exception] = None
        low_confidence = False

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    system=[
                        {
                            "type": "text",
                            "text": _SYSTEM_PROMPT,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    tools=[
                        {
                            **_EXTRACT_TOOL,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    tool_choice={"type": "tool", "name": "extract_test_case"},
                    messages=[
                        {
                            "role": "user",
                            "content": _build_user_message(
                                chunk, trimmed_md, schema_props
                            ),
                        }
                    ],
                )

                tool_input = self._parse_tool_response(response)
                tool_input.setdefault("id", chunk["id"])
                tool_input.setdefault("title", chunk["title"])
                tool_input["source_chunk_id"] = chunk["id"]
                tool_input["page_start"] = chunk["page_start"]
                tool_input["page_end"] = chunk["page_end"]
                tool_input["low_confidence"] = low_confidence

                return TestCase.model_validate(tool_input)

            except (ValidationError, KeyError, ValueError) as exc:
                last_error = exc
                low_confidence = True
                logger.warning(
                    "Async extraction attempt %d/%d failed for '%s': %s",
                    attempt, MAX_RETRIES, chunk["id"], exc,
                )

        raise RuntimeError(
            f"Async LLM extraction failed for chunk '{chunk['id']}' "
            f"after {MAX_RETRIES} attempts: {last_error}"
        )

    def _parse_tool_response(self, response: Any) -> dict:
        for block in response.content:
            if block.type == "tool_use" and block.name == "extract_test_case":
                return dict(block.input)
        raise ValueError("No tool_use block in response")


# ------------------------------------------------------------------ #
# Module-level helpers                                                #
# ------------------------------------------------------------------ #

def _trim_schema(schema: dict) -> dict:
    """
    Return only the `properties` sub-dict from a JSON schema.

    Strips $defs, $schema, title, description, required — which are boilerplate
    and not needed by the LLM for field-name / value accuracy. Reduces schema
    token count by ~50%.

    Returns empty dict if schema has no `properties`.
    """
    return schema.get("properties", {})


def _trim_chunk(markdown: str) -> str:
    """
    Strip noisy content from pymupdf4llm output before sending to LLM.

    Removes:
    - Page-break separators (--- lines)
    - Runs of 3+ blank lines (collapsed to 2)
    """
    text = _PAGE_BREAK_RE.sub("\n\n", markdown)
    text = _WHITESPACE_RE.sub("\n\n", text)
    return text.strip()


def _build_user_message(
    chunk: SectionChunk,
    trimmed_md: str,
    schema_props: dict,
) -> list[dict]:
    """
    Build the user message content list with optional cached schema block.

    Schema block gets cache_control when non-empty — the same action schema
    is often reused across related test cases (e.g. multiple TC_B* tests all
    use BootNotificationRequest.json).
    """
    parts: list[dict] = []

    if schema_props:
        parts.append({
            "type": "text",
            "text": (
                "OCPP field reference (properties only — use for exact names/types):\n"
                f"```json\n{json.dumps(schema_props, indent=2)[:1200]}\n```\n"
            ),
            # Cache schema blocks — same schema often reused for sibling TCs
            "cache_control": {"type": "ephemeral"},
        })

    parts.append({
        "type": "text",
        "text": (
            f"Extract test case from this spec section:\n\n{trimmed_md}"
        ),
        # Do NOT cache — unique per chunk
    })

    return parts
