"""
LLMExtractor — two-step test-case extraction via Anthropic Messages API.

Step 1: Classify the test type (message_sequence, field_validation, etc.)
Step 2: Extract structured TestCase model with mobilityhouse schema as RAG context.

Retries up to MAX_RETRIES times on Pydantic ValidationError.
Uses tool_use (function calling) for reliable JSON extraction.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from pydantic import ValidationError

from spec_to_test.extractors.base import SectionChunk
from spec_to_test.models.testcase import (
    Assertion,
    Direction,
    Precondition,
    Step,
    TestCase,
    TestType,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

# ------------------------------------------------------------------ #
# Tool schema for Step 2: structured TestCase extraction              #
# ------------------------------------------------------------------ #

_EXTRACT_TOOL = {
    "name": "extract_test_case",
    "description": (
        "Extract a structured TestCase from a spec section. "
        "Use exact field names and values from the spec text."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Test case ID, e.g. TC_B01"},
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
                        "description": {"type": "string"},
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
                        "step_number": {"type": "integer"},
                        "description": {"type": "string"},
                        "action": {"type": "string"},
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
                                    "description": {"type": "string"},
                                    "field_path": {"type": "string"},
                                    "expected_value": {"type": "string"},
                                    "operator": {"type": "string"},
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
        "required": ["id", "title", "steps"],
    },
}


class LLMExtractor:
    """
    Extracts a TestCase from a SectionChunk using a two-step LLM call.

    Args:
        client:     Anthropic client instance.
        model:      Model ID (default: claude-sonnet-4-6).
        max_tokens: Max tokens for extraction response.
    """

    def __init__(
        self,
        client: Any,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 2048,
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
        Extract a TestCase from *chunk*.

        Args:
            chunk:          SectionChunk from the PDF extractor.
            schema_context: Mobilityhouse JSON schema dict for RAG injection.
                            May be empty — extraction still proceeds.

        Returns:
            Parsed TestCase Pydantic model.

        Raises:
            RuntimeError: If all retries are exhausted.
        """
        test_type = self._step1_classify(chunk)
        return self._step2_extract(chunk, test_type, schema_context)

    # ------------------------------------------------------------------ #
    # Step 1: classify test type                                          #
    # ------------------------------------------------------------------ #

    def _step1_classify(self, chunk: SectionChunk) -> TestType:
        """Classify the test design technique used in this test case."""
        prompt = (
            "You are analyzing an OCPP test specification section.\n"
            "Classify the primary test design technique into exactly one of:\n"
            "  message_sequence, field_validation, state_transition, "
            "timeout_retry, error_handling, unknown\n\n"
            f"Section title: {chunk['title']}\n\n"
            f"Section content (first 800 chars):\n{chunk['markdown'][:800]}\n\n"
            "Reply with ONLY the technique name, nothing else."
        )
        response = self._client.messages.create(
            model=self._model,
            max_tokens=20,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip().lower()
        try:
            return TestType(raw)
        except ValueError:
            logger.debug("Unknown test type '%s', defaulting to UNKNOWN", raw)
            return TestType.UNKNOWN

    # ------------------------------------------------------------------ #
    # Step 2: structured extraction with retry                            #
    # ------------------------------------------------------------------ #

    def _step2_extract(
        self,
        chunk: SectionChunk,
        test_type: TestType,
        schema_context: dict,
    ) -> TestCase:
        """Extract full TestCase using tool_use, retrying on ValidationError."""
        schema_block = (
            f"\n\nOCPP JSON Schema (ground truth for field names and types):\n"
            f"```json\n{json.dumps(schema_context, indent=2)[:2000]}\n```"
            if schema_context else ""
        )
        prompt = (
            f"You are extracting a structured test case from an OCPP 2.0.1 "
            f"specification section.\n"
            f"Test type (pre-classified): {test_type.value}\n"
            f"{schema_block}\n\n"
            f"Spec section:\n\n{chunk['markdown']}\n\n"
            "Extract every step, assertion, and precondition. "
            "Use exact field names and expected values from the spec. "
            "Do NOT invent or infer values not present in the text."
        )

        last_error: Optional[Exception] = None
        low_confidence = False

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    tools=[_EXTRACT_TOOL],
                    tool_choice={"type": "tool", "name": "extract_test_case"},
                    messages=[{"role": "user", "content": prompt}],
                )
                tool_input = self._parse_tool_response(response)
                # Inject metadata not known to the LLM
                tool_input.setdefault("id", chunk["id"])
                tool_input.setdefault("title", chunk["title"])
                tool_input["test_type"] = test_type.value
                tool_input["source_chunk_id"] = chunk["id"]
                tool_input["page_start"] = chunk["page_start"]
                tool_input["page_end"] = chunk["page_end"]
                tool_input["low_confidence"] = low_confidence

                return TestCase.model_validate(tool_input)

            except (ValidationError, KeyError, ValueError) as exc:
                last_error = exc
                low_confidence = True
                logger.warning(
                    "Step 2 attempt %d/%d failed for chunk '%s': %s",
                    attempt, MAX_RETRIES, chunk["id"], exc,
                )

        raise RuntimeError(
            f"LLM extraction failed for chunk '{chunk['id']}' "
            f"after {MAX_RETRIES} attempts: {last_error}"
        )

    def _parse_tool_response(self, response: Any) -> dict:
        """Extract the tool_use input dict from an Anthropic response."""
        for block in response.content:
            if block.type == "tool_use" and block.name == "extract_test_case":
                return dict(block.input)
        raise ValueError("No tool_use block in response")
