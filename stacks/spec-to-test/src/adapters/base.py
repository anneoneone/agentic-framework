"""
BaseAdapter — abstract interface every spec-type adapter must implement.

All pipeline stages (@pdf-extractor, @ir-modeler, @pytest-generator) consume
adapters through this interface only. No spec-specific logic leaks into other modules.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AdapterConfig:
    """Serializable snapshot of an adapter's configuration (for debug/logging)."""
    spec_id: str
    spec_version: str
    section_pattern_keys: list[str]
    table_column_keys: list[str]


class BaseAdapter(ABC):
    """
    Abstract base for spec-specific parsing adapters.

    Subclasses encapsulate all spec-version knowledge: header regex,
    table column names, action→schema mappings. The rest of the pipeline
    remains spec-agnostic.
    """

    # Class-level identity — subclasses must override
    spec_id: str = ""
    spec_version: str = ""

    # ------------------------------------------------------------------ #
    # Required abstract properties                                         #
    # ------------------------------------------------------------------ #

    @property
    @abstractmethod
    def section_patterns(self) -> dict[str, re.Pattern]:
        """
        Compiled regex patterns keyed by section type.

        Required keys:
            'testcase'       — matches test-case section headers (e.g. TC_B01)
            'reusable_state' — matches reusable-state headers (e.g. RS_001)

        Optional keys (omit if spec doesn't have them):
            'datatype'       — matches datatype definition headers
        """

    @property
    @abstractmethod
    def table_columns(self) -> dict[str, list[str]]:
        """
        Expected column name lists per section type.

        Keys mirror section_patterns keys. Values are lists of canonical
        column names the extraction layer should look for.

        Example: {"testcase": ["Step", "Action", "Expected Result"]}
        """

    @property
    @abstractmethod
    def schema_map(self) -> dict[str, str]:
        """
        Mapping from OCPP-style action name → JSON schema filename.

        Used by SchemaRetriever to load mobilityhouse ground-truth schemas
        for RAG injection into LLM prompts.

        Example: {"BootNotification": "BootNotificationRequest.json"}
        """

    # ------------------------------------------------------------------ #
    # Required abstract methods                                            #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def normalize_field_name(self, raw: str) -> str:
        """
        Map a raw column/field name from the PDF to the canonical IR name.

        Example: "Expected Result" → "expected_result"
        """

    @abstractmethod
    def extract_test_id(self, title: str) -> str | None:
        """
        Extract the canonical test-case ID from a section title string.

        Example: "TC_B01 - Boot Notification" → "TC_B01"
        Returns None if no ID found.
        """

    # ------------------------------------------------------------------ #
    # Concrete helpers (shared by all adapters)                            #
    # ------------------------------------------------------------------ #

    def to_config_dict(self) -> AdapterConfig:
        return AdapterConfig(
            spec_id=self.spec_id,
            spec_version=self.spec_version,
            section_pattern_keys=list(self.section_patterns.keys()),
            table_column_keys=list(self.table_columns.keys()),
        )
