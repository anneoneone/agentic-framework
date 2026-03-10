"""
Unit tests for the spec knowledge base module.

No real PDF, no real Anthropic API, no real Neo4j — all external dependencies
are mocked. sentence_transformers.SentenceTransformer is patched so the model
is never downloaded.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from spec_to_test.extractors.base import SectionChunk
from spec_to_test.knowledge.indexer import SpecKnowledgeIndex, _cosine_sim, _md_hash
from spec_to_test.knowledge.qa_engine import NO_ANSWER, AnswerResult, SpecQAEngine
from spec_to_test.knowledge.memento_bridge import MementoBridge


# ------------------------------------------------------------------ #
# Fixtures                                                             #
# ------------------------------------------------------------------ #

@pytest.fixture
def sample_chunks() -> list[SectionChunk]:
    return [
        {
            "id": "TC_B01",
            "title": "Boot Notification",
            "markdown": "## TC_B01\nPreconditions: CS not connected.\nStep 1: send BootNotificationRequest",
            "page_start": 1,
            "page_end": 2,
            "section_type": "testcase",
        },
        {
            "id": "RS_001",
            "title": "CSMS Simulated State",
            "markdown": "## RS_001\nCSMS simulator running and ready.",
            "page_start": 5,
            "page_end": 5,
            "section_type": "reusable_state",
        },
        {
            "id": "TC_B02",
            "title": "Heartbeat",
            "markdown": "## TC_B02\nCS sends HeartbeatRequest every interval.",
            "page_start": 3,
            "page_end": 4,
            "section_type": "testcase",
        },
    ]


def _fake_encoder(texts, **kwargs):
    """Return deterministic unit vectors — one per input text."""
    rng = np.random.default_rng(seed=42)
    vecs = rng.standard_normal((len(texts), 16)).astype(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / norms


@pytest.fixture
def mock_st(monkeypatch):
    """Patch SentenceTransformer.encode so no model download happens."""
    mock_model = MagicMock()
    mock_model.encode.side_effect = _fake_encoder
    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
        yield mock_model


# ------------------------------------------------------------------ #
# SpecKnowledgeIndex — build                                           #
# ------------------------------------------------------------------ #

def test_build_creates_index_files(tmp_path, sample_chunks, mock_st):
    idx = SpecKnowledgeIndex(tmp_path / "knowledge")
    idx.build(sample_chunks)

    assert (tmp_path / "knowledge" / "chunks.json").exists()
    assert (tmp_path / "knowledge" / "embeddings.npy").exists()
    assert (tmp_path / "knowledge" / "meta.json").exists()


def test_build_stores_all_chunks(tmp_path, sample_chunks, mock_st):
    idx = SpecKnowledgeIndex(tmp_path / "knowledge")
    idx.build(sample_chunks)

    saved = json.loads((tmp_path / "knowledge" / "chunks.json").read_text())
    assert len(saved) == 3
    ids = {c["id"] for c in saved}
    assert ids == {"TC_B01", "RS_001", "TC_B02"}


def test_build_incremental_skips_unchanged(tmp_path, sample_chunks, mock_st):
    kdir = tmp_path / "knowledge"
    idx = SpecKnowledgeIndex(kdir)
    idx.build(sample_chunks)

    call_count_after_first = mock_st.encode.call_count

    # Second build with same chunks — should not re-embed anything
    idx2 = SpecKnowledgeIndex(kdir)
    idx2.build(sample_chunks)

    assert mock_st.encode.call_count == call_count_after_first  # no new encode calls


def test_build_incremental_embeds_new_chunk(tmp_path, sample_chunks, mock_st):
    kdir = tmp_path / "knowledge"
    idx = SpecKnowledgeIndex(kdir)
    idx.build(sample_chunks[:2])  # build with 2 chunks

    call_count_after_first = mock_st.encode.call_count

    # Add one new chunk
    new_chunk: SectionChunk = {
        "id": "TC_C01",
        "title": "Authorize",
        "markdown": "## TC_C01\nCS sends AuthorizeRequest.",
        "page_start": 10,
        "page_end": 10,
        "section_type": "testcase",
    }
    idx2 = SpecKnowledgeIndex(kdir)
    idx2.build(sample_chunks[:2] + [new_chunk])

    # encode must have been called again (for the 1 new chunk)
    assert mock_st.encode.call_count > call_count_after_first
    assert idx2.size == 3


def test_size_and_is_loaded(tmp_path, sample_chunks, mock_st):
    idx = SpecKnowledgeIndex(tmp_path / "knowledge")
    assert not idx.is_loaded

    idx.build(sample_chunks)
    assert idx.is_loaded
    assert idx.size == 3


# ------------------------------------------------------------------ #
# SpecKnowledgeIndex — load                                            #
# ------------------------------------------------------------------ #

def test_load_restores_index(tmp_path, sample_chunks, mock_st):
    kdir = tmp_path / "knowledge"
    idx = SpecKnowledgeIndex(kdir)
    idx.build(sample_chunks)

    # Fresh instance — load from disk
    idx2 = SpecKnowledgeIndex(kdir)
    idx2.load()

    assert idx2.size == 3
    assert idx2.is_loaded


def test_load_raises_when_missing(tmp_path):
    idx = SpecKnowledgeIndex(tmp_path / "nonexistent")
    with pytest.raises(FileNotFoundError, match="--save-knowledge"):
        idx.load()


# ------------------------------------------------------------------ #
# SpecKnowledgeIndex — search                                          #
# ------------------------------------------------------------------ #

def test_search_returns_top_k(tmp_path, sample_chunks, mock_st):
    idx = SpecKnowledgeIndex(tmp_path / "knowledge")
    idx.build(sample_chunks)

    results = idx.search("BootNotification preconditions", top_k=2)

    assert len(results) == 2
    for chunk, score in results:
        assert "id" in chunk
        assert isinstance(score, float)


def test_search_sorted_by_score(tmp_path, sample_chunks, mock_st):
    idx = SpecKnowledgeIndex(tmp_path / "knowledge")
    idx.build(sample_chunks)

    results = idx.search("some query", top_k=3)
    scores = [s for _, s in results]
    assert scores == sorted(scores, reverse=True)


def test_search_raises_when_empty():
    idx = SpecKnowledgeIndex("/tmp/not_used")
    with pytest.raises(RuntimeError, match="empty"):
        idx.search("anything")


# ------------------------------------------------------------------ #
# SpecQAEngine                                                         #
# ------------------------------------------------------------------ #

def _make_qa_engine(tmp_path, sample_chunks, mock_st) -> SpecQAEngine:
    kdir = str(tmp_path / "knowledge")
    idx = SpecKnowledgeIndex(kdir)
    idx.build(sample_chunks)
    return SpecQAEngine(kdir)


def test_ask_returns_answer_result(tmp_path, sample_chunks, mock_st):
    engine = _make_qa_engine(tmp_path, sample_chunks, mock_st)

    mock_response = SimpleNamespace(
        content=[SimpleNamespace(text="BootNotification requires CS not connected.")]
    )
    with patch.object(engine, "_get_client") as mock_client:
        mock_client.return_value.messages.create.return_value = mock_response
        result = engine.ask("What are the preconditions for TC_B01?")

    assert isinstance(result, AnswerResult)
    assert result.answer == "BootNotification requires CS not connected."
    assert len(result.source_chunk_ids) > 0
    assert result.grounded is True


def test_ask_returns_no_answer_when_score_too_low(tmp_path, sample_chunks, mock_st):
    engine = _make_qa_engine(tmp_path, sample_chunks, mock_st)

    # Patch search to return low-score results
    engine._index.search = MagicMock(
        return_value=[(sample_chunks[0], 0.10)]
    )

    result = engine.ask("Something completely unrelated to OCPP")

    assert result.answer == NO_ANSWER
    assert result.grounded is False


# ------------------------------------------------------------------ #
# MementoBridge                                                        #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_index_chunks_async_writes_learnings(sample_chunks):
    bridge = MementoBridge(stack="spec-to-test")

    mock_client = MagicMock()
    mock_client.search_knowledge_graph.return_value = []  # nothing pre-indexed
    mock_client.add_learning.return_value = {"id": "learning_xxx"}

    with patch.object(bridge, "_get_client", return_value=mock_client):
        with patch.object(bridge, "_is_reachable", new_callable=AsyncMock, return_value=True):
            written = await bridge.index_chunks_async(sample_chunks)

    # Both testcase and reusable_state chunks should be written
    assert written == 3
    assert mock_client.add_learning.call_count == 3


@pytest.mark.asyncio
async def test_index_chunks_async_skips_already_indexed(sample_chunks):
    bridge = MementoBridge(stack="spec-to-test")

    mock_client = MagicMock()
    # Simulate all chunks already present in the graph
    mock_client.search_knowledge_graph.side_effect = lambda **kw: [
        {"content": kw["query"]}  # returns a hit matching the chunk ID
    ]
    mock_client.add_learning.return_value = {}

    with patch.object(bridge, "_get_client", return_value=mock_client):
        with patch.object(bridge, "_is_reachable", new_callable=AsyncMock, return_value=True):
            written = await bridge.index_chunks_async(sample_chunks)

    assert written == 0
    mock_client.add_learning.assert_not_called()


@pytest.mark.asyncio
async def test_index_chunks_async_skips_unknown_type():
    bridge = MementoBridge(stack="spec-to-test")

    unknown_chunk: SectionChunk = {
        "id": "UNK_001",
        "title": "Unknown",
        "markdown": "## UNK",
        "page_start": 1,
        "page_end": 1,
        "section_type": "unknown",
    }

    mock_client = MagicMock()
    with patch.object(bridge, "_get_client", return_value=mock_client):
        with patch.object(bridge, "_is_reachable", new_callable=AsyncMock, return_value=True):
            written = await bridge.index_chunks_async([unknown_chunk])

    assert written == 0


@pytest.mark.asyncio
async def test_index_chunks_async_graceful_when_unreachable(sample_chunks):
    bridge = MementoBridge(stack="spec-to-test")

    with patch.object(bridge, "_is_reachable", new_callable=AsyncMock, return_value=False):
        written = await bridge.index_chunks_async(sample_chunks)

    assert written == 0


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def test_md_hash_is_deterministic():
    h1 = _md_hash("hello world")
    h2 = _md_hash("hello world")
    assert h1 == h2


def test_cosine_sim_unit_vectors():
    q = np.array([1.0, 0.0], dtype=np.float32)
    matrix = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    scores = _cosine_sim(q, matrix)
    assert abs(scores[0] - 1.0) < 1e-5
    assert abs(scores[1] - 0.0) < 1e-5
