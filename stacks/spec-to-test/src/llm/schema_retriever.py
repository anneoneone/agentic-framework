"""
SchemaRetriever — loads mobilityhouse/ocpp JSON schemas for RAG injection.

Resolves action names (e.g. "BootNotification") to their JSON schema files
in the installed ocpp package (ocpp/v201/schemas/*.json), returning the schema
dict for inclusion in LLM prompts as ground-truth context.
"""
from __future__ import annotations

import importlib.resources
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from spec_to_test.adapters.base import BaseAdapter

logger = logging.getLogger(__name__)


class SchemaRetriever:
    """
    Retrieves mobilityhouse JSON schemas for a given OCPP action.

    Schemas are loaded from the installed `ocpp` package's v201/schemas/
    directory — the ground truth for field names, types, and constraints.
    """

    def __init__(self, adapter: BaseAdapter) -> None:
        self._adapter = adapter
        self._schema_dir: Optional[Path] = self._resolve_schema_dir()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def get(self, action: str) -> dict:
        """
        Return the JSON schema dict for *action*.

        Args:
            action: OCPP action name, e.g. "BootNotification".

        Returns:
            Parsed schema dict. Empty dict if not found (safe fallback).
        """
        schema_filename = self._adapter.schema_map.get(action)
        if not schema_filename:
            logger.debug("No schema mapping for action '%s'", action)
            return {}

        return self._load_schema(schema_filename)

    def get_for_chunk(self, chunk_markdown: str) -> dict:
        """
        Heuristically detect the OCPP action from chunk text and return schema.

        Scans the markdown for known action names from the adapter's schema_map.
        Returns the first match found, or empty dict.
        """
        for action in self._adapter.schema_map:
            if action in chunk_markdown:
                return self.get(action)
        return {}

    # ------------------------------------------------------------------ #
    # Internals                                                            #
    # ------------------------------------------------------------------ #

    def _resolve_schema_dir(self) -> Optional[Path]:
        """Locate ocpp/v201/schemas/ inside the installed package."""
        try:
            import ocpp  # type: ignore[import-untyped]
            ocpp_root = Path(ocpp.__file__).parent
            schema_dir = ocpp_root / "v201" / "schemas"
            if schema_dir.is_dir():
                logger.debug("Schema dir: %s", schema_dir)
                return schema_dir
            logger.warning("ocpp v201/schemas/ not found at %s", schema_dir)
        except ImportError:
            logger.warning(
                "mobilityhouse/ocpp not installed. "
                "Install: pip install ocpp>=2.0.0"
            )
        return None

    @lru_cache(maxsize=64)
    def _load_schema(self, filename: str) -> dict:
        if self._schema_dir is None:
            return {}
        path = self._schema_dir / filename
        if not path.exists():
            logger.warning("Schema file not found: %s", path)
            return {}
        with open(path) as f:
            return json.load(f)
