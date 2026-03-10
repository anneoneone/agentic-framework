"""
IR models for test cases.

TestCase    — one complete test scenario from the spec
Step        — one message-exchange step within a test case
Assertion   — a verifiable claim within a step
Precondition — a condition that must hold before the test runs
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TestType(str, Enum):
    """OCPP test design technique (classified in LLM Step 1)."""
    MESSAGE_SEQUENCE = "message_sequence"
    FIELD_VALIDATION = "field_validation"
    STATE_TRANSITION = "state_transition"
    TIMEOUT_RETRY = "timeout_retry"
    ERROR_HANDLING = "error_handling"
    UNKNOWN = "unknown"


class Direction(str, Enum):
    """Message direction in a step."""
    CS_TO_CSMS = "CS→CSMS"
    CSMS_TO_CS = "CSMS→CS"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


class Assertion(BaseModel):
    """A verifiable claim that must hold after a step executes."""
    description: str
    field_path: Optional[str] = None     # e.g. "response.registrationStatus"
    expected_value: Optional[str] = None  # raw string; codegen maps to enum member
    operator: str = "eq"                  # eq | neq | contains | in | notnull
    low_confidence: bool = False          # flagged for human review


class Step(BaseModel):
    """One ordered step in a test case (typically one message exchange)."""
    step_number: int
    description: str
    action: str                           # e.g. "Send BootNotificationRequest"
    message_type: Optional[str] = None   # e.g. "BootNotification"
    direction: Direction = Direction.UNKNOWN
    assertions: list[Assertion] = Field(default_factory=list)
    reusable_state_refs: list[str] = Field(default_factory=list)


class Precondition(BaseModel):
    """A condition the test environment must satisfy before execution."""
    description: str
    reusable_state_ref: Optional[str] = None  # e.g. "RS_001"


class TestCase(BaseModel):
    """
    One test case from the spec, fully parsed into the IR.

    Maps 1:1 to a generated pytest test function.
    """
    id: str                        # e.g. "TC_B01"
    title: str
    test_type: TestType = TestType.UNKNOWN
    preconditions: list[Precondition] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    expected_outcome: str = ""
    source_chunk_id: str = ""      # SectionChunk.id this was extracted from
    page_start: int = 0
    page_end: int = 0
    low_confidence: bool = False   # True if LLM extraction had repeated retries
