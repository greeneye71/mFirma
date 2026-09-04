from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class JobStatus(StrEnum):
    PENDING = "in_attesa"
    CHECKING = "controllo"
    SIGNING = "firma"
    SUCCEEDED = "riuscito"
    SKIPPED = "saltato"
    FAILED = "errore"
    CANCELLED = "annullato"


@dataclass(frozen=True, slots=True)
class DocumentCandidate:
    source: Path
    person: str | None
    size: int
    modified_ns: int

    @classmethod
    def from_path(cls, source: Path, person: str | None = None) -> "DocumentCandidate":
        resolved = source.expanduser().resolve(strict=True)
        stat = resolved.stat()
        return cls(resolved, person, stat.st_size, stat.st_mtime_ns)


@dataclass(frozen=True, slots=True)
class SignaturePlacement:
    page_index: int
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(slots=True)
class SignJob:
    document: DocumentCandidate
    destination: Path
    status: JobStatus = JobStatus.PENDING
    error_code: str | None = None
    message: str = ""


@dataclass(frozen=True, slots=True)
class PageGeometry:
    lower_left_x: float
    lower_left_y: float
    upper_right_x: float
    upper_right_y: float
    rotation: int = 0

    @property
    def width(self) -> float:
        return self.upper_right_x - self.lower_left_x

    @property
    def height(self) -> float:
        return self.upper_right_y - self.lower_left_y

