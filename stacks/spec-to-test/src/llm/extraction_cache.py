"""
ExtractionCache — skip LLM calls for chunks already extracted in a previous run.

How it works:
  - Cache key: SHA-256 of (chunk.markdown + model_id)
  - Cache value: serialized TestCase JSON
  - Store: JSON file at <cache_dir>/extractions.json  (human-readable, versionable)

Why this is safe for accuracy:
  - Cache is keyed on the exact chunk content + model. If the spec PDF changes,
    or the model changes, the hash changes and extraction re-runs.
  - Cache entries are never mutated — only written once on first successful extract.
  - low_confidence=True entries are always re-extracted (not cached).
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

from spec_to_test.models.testcase import TestCase

logger = logging.getLogger(__name__)

_CACHE_FILENAME = "extractions.json"


class ExtractionCache:
    """
    Persistent, file-backed cache for LLM extraction results.

    Args:
        cache_dir: Directory where extractions.json is stored.
                   Created if it does not exist.
        model_id:  Model used for extraction — included in cache key so that
                   changing the model invalidates all cached entries.
    """

    def __init__(self, cache_dir: str | Path, model_id: str) -> None:
        self._path = Path(cache_dir) / _CACHE_FILENAME
        self._model_id = model_id
        self._store: dict[str, dict] = self._load()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def get(self, chunk_markdown: str) -> Optional[TestCase]:
        """
        Return cached TestCase if available, else None.

        Never returns low_confidence entries — they are always re-extracted.
        """
        key = self._key(chunk_markdown)
        entry = self._store.get(key)
        if entry is None:
            return None

        tc = TestCase.model_validate(entry)
        if tc.low_confidence:
            logger.debug("Cache hit but low_confidence — re-extracting")
            return None

        logger.debug("Cache hit for key %s…", key[:12])
        return tc

    def put(self, chunk_markdown: str, test_case: TestCase) -> None:
        """
        Store a successfully extracted TestCase.

        low_confidence entries are NOT cached — they should be re-tried
        on the next run to see if the model does better.
        """
        if test_case.low_confidence:
            return
        key = self._key(chunk_markdown)
        self._store[key] = test_case.model_dump(mode="json")
        self._save()
        logger.debug("Cached extraction for key %s…", key[:12])

    def size(self) -> int:
        return len(self._store)

    def clear(self) -> None:
        self._store = {}
        self._save()
        logger.info("Extraction cache cleared")

    # ------------------------------------------------------------------ #
    # Internals                                                            #
    # ------------------------------------------------------------------ #

    def _key(self, chunk_markdown: str) -> str:
        """SHA-256 of chunk content + model_id."""
        raw = f"{self._model_id}::{chunk_markdown}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _load(self) -> dict[str, dict]:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                logger.debug("Loaded %d cached extractions from %s", len(data), self._path)
                return data
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Cache file corrupted, starting fresh: %s", exc)
        return {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._store, indent=2), encoding="utf-8"
        )
