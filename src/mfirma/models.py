from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Mapping


class JobStatus(StrEnum):
    PENDING = "in_attesa"
    CHECKING = "controllo"
    SIGNING = "firma"
    SUCCEEDED = "riuscito"
    SKIPPED = "saltato"
    FAILED = "errore"
    CANCELLED = "annullato"


class BatchPhase(StrEnum):
    PREPARING = "preparazione"
    CHECKING = "controllo"
    SIGNING = "firma"
    VERIFYING = "verifica"
    PUBLISHING = "pubblicazione"
    COMPLETED = "completato"


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


@dataclass(frozen=True, slots=True)
class DisplayRect:
    """Rettangolo in punti sulla pagina visualizzata, con origine in basso a sinistra."""

    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class NormalizedDisplayRect:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        values = (self.x, self.y, self.width, self.height)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("Le coordinate normalizzate devono essere finite")
        if any(value < 0 or value > 1 for value in values):
            raise ValueError("Le coordinate normalizzate devono essere tra 0 e 1")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Le dimensioni normalizzate devono essere positive")
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("Il riquadro normalizzato deve essere dentro la pagina")


@dataclass(frozen=True, slots=True)
class SignaturePositionPlan:
    placements: Mapping[str, SignaturePlacement]
    shared_rect: NormalizedDisplayRect | None = None


@dataclass(slots=True)
class SignJob:
    document: DocumentCandidate
    destination: Path
    status: JobStatus = JobStatus.PENDING
    error_code: str | None = None
    message: str = ""
    operation_id: str = ""
    batch_id: str = ""
    completed_at: str = ""
    signed_at: str = ""
    output_sha256: str = ""
    signature_saved: bool = False
    register_error: bool = False


@dataclass(frozen=True, slots=True)
class BatchProgress:
    index: int
    total: int
    completed: int
    phase: BatchPhase
    job: SignJob


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
