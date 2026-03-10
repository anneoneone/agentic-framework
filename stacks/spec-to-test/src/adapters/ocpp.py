"""
OCPPAdapter — OCPP 2.0.1 Part 6 concrete adapter.

Encapsulates all OCPP-specific parsing knowledge:
- TC_*/RS_* section header patterns
- Expected table column names
- Action → mobilityhouse schema file mapping
- Field name normalisation
"""
from __future__ import annotations

import re

from .base import BaseAdapter


class OCPPAdapter(BaseAdapter):
    """
    Adapter for OCPP 2.0.1 Edition 4 Part 6 (Test Cases & Examples).

    Test-case IDs follow the pattern TC_<letter><digits>[_<sub>]
    e.g. TC_B01, TC_B01_01, TC_C02_03

    Reusable state IDs: RS_<digits>  e.g. RS_001
    """

    spec_id = "ocpp"
    spec_version = "2.0.1"

    # ------------------------------------------------------------------ #
    # Section patterns                                                     #
    # ------------------------------------------------------------------ #

    @property
    def section_patterns(self) -> dict[str, re.Pattern]:
        return {
            # Matches H2/H3 Markdown headers containing TC_ identifiers
            # Examples: "## TC_B01 - Boot Notification"
            #           "### TC_B01_01 Boot Notification – Happy Flow"
            "testcase": re.compile(
                r"^#{1,3}\s+(TC[_-][A-Z]\d+(?:[_-]\d+)*)\s*[-–—]?\s*(.+)$",
                re.MULTILINE,
            ),
            # Matches reusable-state headers
            # Example: "## RS_001 - CSMS Simulated State"
            "reusable_state": re.compile(
                r"^#{1,3}\s+(RS[_-]\d+)\s*[-–—]?\s*(.+)$",
                re.MULTILINE,
            ),
        }

    # ------------------------------------------------------------------ #
    # Table columns                                                        #
    # ------------------------------------------------------------------ #

    @property
    def table_columns(self) -> dict[str, list[str]]:
        return {
            "testcase": [
                "Step",
                "Action",
                "Expected Result",
                "Message",
                "Field",
                "Value",
            ],
            "reusable_state": [
                "Condition",
                "Description",
            ],
        }

    # ------------------------------------------------------------------ #
    # Schema map: action → mobilityhouse JSON schema filename              #
    # Only *Request schemas are needed for RAG (response schemas also      #
    # included for validation-step test cases).                            #
    # ------------------------------------------------------------------ #

    @property
    def schema_map(self) -> dict[str, str]:
        return {
            # Core
            "BootNotification": "BootNotificationRequest.json",
            "StatusNotification": "StatusNotificationRequest.json",
            "Heartbeat": "HeartbeatRequest.json",
            # Authorization
            "Authorize": "AuthorizeRequest.json",
            # Transactions
            "TransactionEvent": "TransactionEventRequest.json",
            "RequestStartTransaction": "RequestStartTransactionRequest.json",
            "RequestStopTransaction": "RequestStopTransactionRequest.json",
            # Remote control
            "Reset": "ResetRequest.json",
            "ChangeAvailability": "ChangeAvailabilityRequest.json",
            "UnlockConnector": "UnlockConnectorRequest.json",
            "TriggerMessage": "TriggerMessageRequest.json",
            # Configuration
            "GetVariables": "GetVariablesRequest.json",
            "SetVariables": "SetVariablesRequest.json",
            "GetBaseReport": "GetBaseReportRequest.json",
            "NotifyReport": "NotifyReportRequest.json",
            # Security / certificates
            "SignCertificate": "SignCertificateRequest.json",
            "CertificateSigned": "CertificateSignedRequest.json",
            "InstallCertificate": "InstallCertificateRequest.json",
            "GetInstalledCertificateIds": "GetInstalledCertificateIdsRequest.json",
            "DeleteCertificate": "DeleteCertificateRequest.json",
            # Smart charging
            "SetChargingProfile": "SetChargingProfileRequest.json",
            "GetChargingProfiles": "GetChargingProfilesRequest.json",
            "ClearChargingProfile": "ClearChargingProfileRequest.json",
            "ReportChargingProfiles": "ReportChargingProfilesRequest.json",
            # Local auth list
            "GetLocalListVersion": "GetLocalListVersionRequest.json",
            "SendLocalList": "SendLocalListRequest.json",
            # Diagnostics / firmware
            "GetLog": "GetLogRequest.json",
            "LogStatusNotification": "LogStatusNotificationRequest.json",
            "UpdateFirmware": "UpdateFirmwareRequest.json",
            "FirmwareStatusNotification": "FirmwareStatusNotificationRequest.json",
            # Reservation
            "ReserveNow": "ReserveNowRequest.json",
            "CancelReservation": "CancelReservationRequest.json",
            # Display
            "SetDisplayMessage": "SetDisplayMessageRequest.json",
            "GetDisplayMessages": "GetDisplayMessagesRequest.json",
            "ClearDisplayMessage": "ClearDisplayMessageRequest.json",
            # Customer info
            "CustomerInformation": "CustomerInformationRequest.json",
            "NotifyCustomerInformation": "NotifyCustomerInformationRequest.json",
            # Data transfer
            "DataTransfer": "DataTransferRequest.json",
        }

    # ------------------------------------------------------------------ #
    # Field name normalisation                                             #
    # ------------------------------------------------------------------ #

    _FIELD_MAP: dict[str, str] = {
        "Expected Result": "expected_result",
        "Action": "action",
        "Step": "step_number",
        "Message": "message_type",
        "Field": "field_name",
        "Value": "field_value",
        "Condition": "condition",
        "Description": "description",
    }

    def normalize_field_name(self, raw: str) -> str:
        cleaned = raw.strip()
        if cleaned in self._FIELD_MAP:
            return self._FIELD_MAP[cleaned]
        # Fallback: lowercase + underscores
        return re.sub(r"\s+", "_", cleaned.lower())

    # ------------------------------------------------------------------ #
    # Test-case ID extraction                                              #
    # ------------------------------------------------------------------ #

    _TC_ID_RE = re.compile(r"\b(TC[_-][A-Z]\d+(?:[_-]\d+)*)\b")

    def extract_test_id(self, title: str) -> str | None:
        m = self._TC_ID_RE.search(title)
        return m.group(1) if m else None
