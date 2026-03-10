"""
IR model for reusable states.

ReusableState maps to a pytest fixture in conftest.py.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class StateCondition(BaseModel):
    """One condition that defines the reusable state."""
    condition: str
    description: str


class ReusableState(BaseModel):
    """
    A reusable pre-condition block from the spec.

    Maps to a @pytest.fixture in the generated conftest.py.
    """
    id: str                                       # e.g. "RS_001"
    title: str
    conditions: list[StateCondition] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)  # other RS IDs
    source_chunk_id: str = ""
    page_start: int = 0
    page_end: int = 0
