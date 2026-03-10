"""
Unit tests for the PDF extraction layer.

Tests run without a real PDF — use synthetic Markdown strings and the
sample_chunks.json fixture.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from spec_to_test.adapters.ocpp import OCPPAdapter
from spec_to_test.extractors.base import SectionChunk
from spec_to_test.extractors.ocpp import detect_toc_offset, normalise_tc_id
from spec_to_test.extractors.pipeline import PdfExtractionPipeline

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def adapter():
    return OCPPAdapter()


@pytest.fixture
def pipeline():
    return PdfExtractionPipeline()


@pytest.fixture
def sample_chunks() -> list[dict]:
    return json.loads((FIXTURES_DIR / "sample_chunks.json").read_text())


# ------------------------------------------------------------------ #
# split_markdown_sections                                             #
# ------------------------------------------------------------------ #

SYNTHETIC_MD = """\
# OCPP 2.0.1 Part 6

Some intro text.

## TC_B01 - Boot Notification

Preconditions: CS not connected.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Connect | WebSocket established |

## TC_B02 - Status Notification

Another test case.

## RS_001 - CSMS State

Reusable state description.
"""


def test_split_sections_detects_testcases(pipeline, adapter):
    chunks = pipeline.split_markdown_sections(SYNTHETIC_MD, adapter)
    tc_ids = [c["id"] for c in chunks if c["section_type"] == "testcase"]
    assert "TC_B01" in tc_ids
    assert "TC_B02" in tc_ids


def test_split_sections_detects_reusable_states(pipeline, adapter):
    chunks = pipeline.split_markdown_sections(SYNTHETIC_MD, adapter)
    rs_ids = [c["id"] for c in chunks if c["section_type"] == "reusable_state"]
    assert "RS_001" in rs_ids


def test_split_sections_correct_count(pipeline, adapter):
    chunks = pipeline.split_markdown_sections(SYNTHETIC_MD, adapter)
    assert len(chunks) == 3


def test_split_sections_content_integrity(pipeline, adapter):
    chunks = pipeline.split_markdown_sections(SYNTHETIC_MD, adapter)
    b01 = next(c for c in chunks if c["id"] == "TC_B01")
    assert "Boot Notification" in b01["title"]
    assert "WebSocket established" in b01["markdown"]


def test_split_sections_no_unknown_type(pipeline, adapter):
    chunks = pipeline.split_markdown_sections(SYNTHETIC_MD, adapter)
    for chunk in chunks:
        assert chunk["section_type"] != "unknown"


# ------------------------------------------------------------------ #
# pdfplumber fallback path                                            #
# ------------------------------------------------------------------ #

def test_extract_raises_on_missing_file(pipeline, adapter):
    with pytest.raises(FileNotFoundError):
        pipeline.extract("/nonexistent/path.pdf", adapter)


def test_extract_calls_pymupdf4llm(pipeline, adapter, tmp_path):
    """Verify the primary path calls pymupdf4llm.to_markdown."""
    fake_pdf = tmp_path / "test.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4")  # minimal valid-looking file

    with patch("pymupdf4llm.to_markdown", return_value=SYNTHETIC_MD) as mock_md:
        chunks = pipeline.extract(str(fake_pdf), adapter)
        mock_md.assert_called_once_with(str(fake_pdf))
    assert len(chunks) == 3


def test_extract_raises_without_pymupdf4llm(pipeline, adapter, tmp_path):
    fake_pdf = tmp_path / "test.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4")

    with patch.dict("sys.modules", {"pymupdf4llm": None}):
        with pytest.raises(ImportError, match="pymupdf4llm"):
            pipeline.extract(str(fake_pdf), adapter)


# ------------------------------------------------------------------ #
# TC_ID extraction                                                    #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("title,expected_id", [
    ("TC_B01 - Boot Notification", "TC_B01"),
    ("## TC_B01_01 Boot Notification – Happy Flow", "TC_B01_01"),
    ("TC-C02 Status Notification", "TC_C02"),
    ("No ID here", None),
])
def test_extract_test_id(adapter, title, expected_id):
    assert adapter.extract_test_id(title) == expected_id


# ------------------------------------------------------------------ #
# Sample fixtures schema validation                                   #
# ------------------------------------------------------------------ #

def test_sample_chunks_schema(sample_chunks):
    required_keys = {"id", "title", "markdown", "page_start", "page_end", "section_type"}
    for chunk in sample_chunks:
        assert required_keys.issubset(chunk.keys()), f"Missing keys in {chunk}"
        assert chunk["section_type"] in ("testcase", "reusable_state", "unknown")
        assert isinstance(chunk["page_start"], int)
        assert isinstance(chunk["page_end"], int)


def test_sample_chunks_has_testcase_and_state(sample_chunks):
    types = {c["section_type"] for c in sample_chunks}
    assert "testcase" in types
    assert "reusable_state" in types


# ------------------------------------------------------------------ #
# OCPP-specific helpers                                               #
# ------------------------------------------------------------------ #

def test_normalise_tc_id():
    assert normalise_tc_id("tc_b01") == "TC_B01"
    assert normalise_tc_id("TC-B01-01") == "TC_B01_01"


def test_detect_toc_offset_no_match():
    assert detect_toc_offset("no table of contents here") == 0
