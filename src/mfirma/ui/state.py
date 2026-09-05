from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from ..models import DocumentCandidate


class ScanState(StrEnum):
    IDLE = "idle"
    SCANNING = "scanning"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    AVAILABLE_WITH_WARNINGS = "available_with_warnings"


class DeviceState(StrEnum):
    UNKNOWN = "unknown"
    DETECTING = "detecting"
    READY = "ready"
    MISSING = "missing"
    MIDDLEWARE_ERROR = "middleware_error"
    CERTIFICATE_MISSING = "certificate_missing"


def normalized_path(path: Path) -> str:
    absolute = os.path.abspath(os.path.expanduser(str(path)))
    return os.path.normcase(absolute).casefold()


@dataclass(slots=True)
class UiState:
    documents: list[DocumentCandidate] = field(default_factory=list)
    selected_paths: set[str] = field(default_factory=set)
    active_person: str | None = None
    search_text: str = ""
    scan_state: ScanState = ScanState.IDLE
    device_state: DeviceState = DeviceState.UNKNOWN
