"""
SpecDocument — top-level IR container.

Serialized to JSON as the checkpoint between extraction and code generation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .state import ReusableState
from .testcase import TestCase


class SpecDocument(BaseModel):
    """
    Complete intermediate representation of a parsed spec PDF.

    ir_version tracks breaking schema changes. Bump when TestCase or
    ReusableState models change in ways that break PytestGenerator.
    """
    spec_id: str               # e.g. "ocpp-2.0.1-part6"
    spec_version: str          # e.g. "2.0.1"
    ir_version: str = "1.0"
    source_pdf: str = ""       # original pdf_path for traceability
    extracted_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    test_cases: list[TestCase] = Field(default_factory=list)
    reusable_states: list[ReusableState] = Field(default_factory=list)

    # Extraction diagnostics
    total_chunks_processed: int = 0
    low_confidence_count: int = 0
    failed_chunk_ids: list[str] = Field(default_factory=list)

    def summary(self) -> str:
        return (
            f"SpecDocument({self.spec_id} v{self.spec_version}, IR {self.ir_version}): "
            f"{len(self.test_cases)} test cases, "
            f"{len(self.reusable_states)} reusable states, "
            f"{self.low_confidence_count} low-confidence"
        )
