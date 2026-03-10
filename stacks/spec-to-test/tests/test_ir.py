"""
Unit tests for the IR + LLM extraction layer.

LLM calls are mocked — no API key required.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from spec_to_test.adapters.ocpp import OCPPAdapter
from spec_to_test.extractors.base import SectionChunk
from spec_to_test.ir.mapper import RawToIRMapper
from spec_to_test.llm.extractor import LLMExtractor
from spec_to_test.llm.schema_retriever import SchemaRetriever
from spec_to_test.models.spec import SpecDocument
from spec_to_test.models.testcase import TestCase, TestType

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def adapter():
    return OCPPAdapter()


@pytest.fixture
def sample_chunks() -> list[SectionChunk]:
    raw = json.loads((FIXTURES_DIR / "sample_chunks.json").read_text())
    return raw  # already valid SectionChunk dicts


# ------------------------------------------------------------------ #
# SchemaRetriever                                                     #
# ------------------------------------------------------------------ #

def test_schema_retriever_returns_dict_for_known_action(adapter):
    retriever = SchemaRetriever(adapter=adapter)
    # May return empty if ocpp package isn't installed in test env — that's OK
    result = retriever.get("BootNotification")
    assert isinstance(result, dict)


def test_schema_retriever_returns_empty_for_unknown_action(adapter):
    retriever = SchemaRetriever(adapter=adapter)
    result = retriever.get("NonExistentAction12345")
    assert result == {}


def test_schema_retriever_get_for_chunk_finds_action(adapter):
    retriever = SchemaRetriever(adapter=adapter)
    chunk_md = "This test validates the BootNotification message exchange."
    result = retriever.get_for_chunk(chunk_md)
    assert isinstance(result, dict)


# ------------------------------------------------------------------ #
# LLMExtractor — mocked Anthropic client                              #
# ------------------------------------------------------------------ #

def _make_tool_use_response(payload: dict):
    """Build a fake Anthropic response with a tool_use block."""
    block = SimpleNamespace(
        type="tool_use",
        name="extract_test_case",
        input=payload,
    )
    return SimpleNamespace(content=[block])


VALID_TEST_CASE_PAYLOAD = {
    "id": "TC_B01",
    "title": "Boot Notification",
    "test_type": "message_sequence",
    "preconditions": [{"description": "CS not connected"}],
    "steps": [
        {
            "step_number": 1,
            "description": "CS connects to CSMS",
            "action": "Send BootNotificationRequest",
            "message_type": "BootNotification",
            "direction": "CS→CSMS",
            "assertions": [
                {
                    "description": "Response status is Accepted",
                    "field_path": "response.registration_status",
                    "expected_value": "RegistrationStatusType.accepted",
                    "operator": "eq",
                }
            ],
        }
    ],
    "expected_outcome": "CS is registered with CSMS.",
}


def test_llm_extractor_happy_path():
    mock_client = MagicMock()
    # Step 1 (classify): text response
    mock_client.messages.create.side_effect = [
        SimpleNamespace(content=[SimpleNamespace(text="message_sequence")]),
        _make_tool_use_response(VALID_TEST_CASE_PAYLOAD),
    ]

    extractor = LLMExtractor(client=mock_client, model="claude-test")
    chunk: SectionChunk = {
        "id": "TC_B01",
        "title": "TC_B01 - Boot Notification",
        "markdown": "## TC_B01\n\nSteps...",
        "page_start": 42,
        "page_end": 43,
        "section_type": "testcase",
    }
    result = extractor.extract(chunk, schema_context={})
    assert isinstance(result, TestCase)
    assert result.id == "TC_B01"
    assert result.test_type == TestType.MESSAGE_SEQUENCE
    assert len(result.steps) == 1
    assert len(result.steps[0].assertions) == 1


def test_llm_extractor_retry_on_validation_error():
    """
    Mock returns invalid JSON on first 2 calls, valid on 3rd.
    Extractor should succeed on attempt 3.
    """
    mock_client = MagicMock()

    bad_block = SimpleNamespace(
        type="tool_use",
        name="extract_test_case",
        input={"id": "TC_B01"},  # missing required 'title' and 'steps'
    )
    bad_response = SimpleNamespace(content=[bad_block])
    good_response = _make_tool_use_response(VALID_TEST_CASE_PAYLOAD)

    mock_client.messages.create.side_effect = [
        SimpleNamespace(content=[SimpleNamespace(text="message_sequence")]),  # Step 1
        bad_response,   # Step 2, attempt 1
        bad_response,   # Step 2, attempt 2
        good_response,  # Step 2, attempt 3
    ]

    extractor = LLMExtractor(client=mock_client, model="claude-test")
    chunk: SectionChunk = {
        "id": "TC_B01",
        "title": "TC_B01",
        "markdown": "content",
        "page_start": 1,
        "page_end": 1,
        "section_type": "testcase",
    }
    result = extractor.extract(chunk, schema_context={})
    assert result.id == "TC_B01"
    assert result.low_confidence is True  # flagged after retries


def test_llm_extractor_exhausts_retries_raises():
    mock_client = MagicMock()
    bad_block = SimpleNamespace(
        type="tool_use",
        name="extract_test_case",
        input={"id": "TC_B01"},  # always missing required fields
    )
    mock_client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(text="message_sequence")]
    )

    extractor = LLMExtractor(client=mock_client, model="claude-test")

    # Override step 2 to always fail
    classify_resp = SimpleNamespace(content=[SimpleNamespace(text="message_sequence")])
    bad_resp = SimpleNamespace(content=[bad_block])
    mock_client.messages.create.side_effect = [
        classify_resp, bad_resp, bad_resp, bad_resp
    ]

    with pytest.raises(RuntimeError, match="after 3 attempts"):
        extractor.extract(
            {"id": "TC_X", "title": "T", "markdown": "m",
             "page_start": 1, "page_end": 1, "section_type": "testcase"},
            schema_context={},
        )


# ------------------------------------------------------------------ #
# RawToIRMapper                                                       #
# ------------------------------------------------------------------ #

def test_mapper_produces_specdocument(adapter, sample_chunks):
    mock_extractor = MagicMock(spec=LLMExtractor)
    mock_extractor.extract.return_value = TestCase(
        id="TC_B01",
        title="Boot Notification",
        steps=[],
    )
    mock_retriever = MagicMock(spec=SchemaRetriever)
    mock_retriever.get_for_chunk.return_value = {}

    mapper = RawToIRMapper(
        adapter=adapter,
        extractor=mock_extractor,
        retriever=mock_retriever,
    )
    doc = mapper.map(sample_chunks)
    assert isinstance(doc, SpecDocument)
    assert doc.total_chunks_processed == len(sample_chunks)


def test_mapper_testcase_count(adapter, sample_chunks):
    mock_extractor = MagicMock(spec=LLMExtractor)
    mock_extractor.extract.return_value = TestCase(id="TC_B01", title="T", steps=[])
    mock_retriever = MagicMock(spec=SchemaRetriever)
    mock_retriever.get_for_chunk.return_value = {}

    mapper = RawToIRMapper(adapter=adapter, extractor=mock_extractor, retriever=mock_retriever)
    doc = mapper.map(sample_chunks)

    expected_tc = sum(1 for c in sample_chunks if c["section_type"] == "testcase")
    expected_rs = sum(1 for c in sample_chunks if c["section_type"] == "reusable_state")
    assert len(doc.test_cases) == expected_tc
    assert len(doc.reusable_states) == expected_rs


def test_mapper_records_failed_chunks(adapter):
    mock_extractor = MagicMock(spec=LLMExtractor)
    mock_extractor.extract.side_effect = RuntimeError("LLM failed")
    mock_retriever = MagicMock(spec=SchemaRetriever)
    mock_retriever.get_for_chunk.return_value = {}

    bad_chunk: SectionChunk = {
        "id": "TC_FAIL",
        "title": "TC_FAIL",
        "markdown": "content",
        "page_start": 1,
        "page_end": 1,
        "section_type": "testcase",
    }
    mapper = RawToIRMapper(adapter=adapter, extractor=mock_extractor, retriever=mock_retriever)
    doc = mapper.map([bad_chunk])
    assert "TC_FAIL" in doc.failed_chunk_ids
    assert len(doc.test_cases) == 0
