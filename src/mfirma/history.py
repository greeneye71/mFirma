from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .config import default_config_path
from .models import JobStatus, SignJob


HISTORY_VERSION = 1
DEFAULT_HISTORY_LIMIT = 100
_TERMINAL_STATUSES = {
    JobStatus.SUCCEEDED,
    JobStatus.FAILED,
    JobStatus.SKIPPED,
    JobStatus.CANCELLED,
}


@dataclass(frozen=True, slots=True)
class HistoryJob:
    source: str
    person: str | None
    status: JobStatus
    output: str
    error_code: str | None

    @classmethod
    def from_job(cls, job: SignJob) -> "HistoryJob":
        if job.status not in _TERMINAL_STATUSES:
            raise ValueError("La cronologia accetta soltanto esiti definitivi")
        return cls(
            source=str(job.document.source),
            person=job.document.person,
            status=job.status,
            output=str(job.destination) if job.status is JobStatus.SUCCEEDED or job.signature_saved else "",
            error_code="REGISTER_WRITE_FAILED" if job.register_error else job.error_code,
        )

    @classmethod
    def from_dict(cls, raw: Any) -> "HistoryJob":
        if not isinstance(raw, dict) or set(raw) != {
            "source",
            "person",
            "status",
            "output",
            "error_code",
        }:
            raise ValueError("Formato esito cronologia non valido")
        source = raw["source"]
        person = raw["person"]
        output = raw["output"]
        error_code = raw["error_code"]
        if not isinstance(source, str) or not source:
            raise ValueError("Percorso sorgente cronologia non valido")
        if person is not None and not isinstance(person, str):
            raise ValueError("Persona cronologia non valida")
        if not isinstance(output, str):
            raise ValueError("Percorso output cronologia non valido")
        if error_code is not None and not isinstance(error_code, str):
            raise ValueError("Codice errore cronologia non valido")
        try:
            status = JobStatus(raw["status"])
        except (TypeError, ValueError) as exc:
            raise ValueError("Stato cronologia non valido") from exc
        if status not in _TERMINAL_STATUSES:
            raise ValueError("Stato cronologia non definitivo")
        if status is JobStatus.SUCCEEDED and not output:
            raise ValueError("Un esito riuscito deve indicare l'output")
        if status is not JobStatus.SUCCEEDED and output and error_code not in {"SOURCE_DELETE_FAILED", "REGISTER_WRITE_FAILED"}:
            raise ValueError("Un esito non riuscito non può avere un output")
        return cls(source, person, status, output, error_code)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "person": self.person,
            "status": self.status.value,
            "output": self.output,
            "error_code": self.error_code,
        }


@dataclass(frozen=True, slots=True)
class BatchHistoryRecord:
    batch_id: str
    created_at: str
    certificate_label: str
    jobs: tuple[HistoryJob, ...]

    @classmethod
    def from_jobs(
        cls,
        jobs: Iterable[SignJob],
        *,
        certificate_label: str,
        created_at: datetime | None = None,
        batch_id: str | None = None,
    ) -> "BatchHistoryRecord":
        timestamp = created_at or datetime.now().astimezone()
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("La data del batch deve includere il fuso orario")
        history_jobs = tuple(HistoryJob.from_job(job) for job in jobs)
        if not history_jobs:
            raise ValueError("Non è possibile archiviare un batch vuoto")
        identifier = batch_id or str(uuid.uuid4())
        cls._validate_id(identifier)
        return cls(
            identifier,
            timestamp.isoformat(timespec="seconds"),
            certificate_label.strip(),
            history_jobs,
        )

    @classmethod
    def from_dict(cls, raw: Any) -> "BatchHistoryRecord":
        if not isinstance(raw, dict) or set(raw) != {
            "batch_id",
            "created_at",
            "certificate_label",
            "jobs",
        }:
            raise ValueError("Formato batch cronologia non valido")
        batch_id = raw["batch_id"]
        created_at = raw["created_at"]
        certificate_label = raw["certificate_label"]
        jobs = raw["jobs"]
        if not isinstance(batch_id, str):
            raise ValueError("Identificativo batch non valido")
        cls._validate_id(batch_id)
        if not isinstance(created_at, str):
            raise ValueError("Data batch non valida")
        try:
            parsed = datetime.fromisoformat(created_at)
        except ValueError as exc:
            raise ValueError("Data batch non valida") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("La data del batch deve includere il fuso orario")
        if not isinstance(certificate_label, str):
            raise ValueError("Certificato cronologia non valido")
        if not isinstance(jobs, list) or not jobs:
            raise ValueError("Elenco esiti cronologia non valido")
        return cls(
            batch_id,
            created_at,
            certificate_label,
            tuple(HistoryJob.from_dict(job) for job in jobs),
        )

    @staticmethod
    def _validate_id(value: str) -> None:
        try:
            parsed = uuid.UUID(value)
        except (ValueError, AttributeError) as exc:
            raise ValueError("Identificativo batch non valido") from exc
        if str(parsed) != value:
            raise ValueError("Identificativo batch non canonico")

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "created_at": self.created_at,
            "certificate_label": self.certificate_label,
            "jobs": [job.to_dict() for job in self.jobs],
        }

    @property
    def counts(self) -> Counter[JobStatus]:
        return Counter(job.status for job in self.jobs)

    @property
    def outcome(self) -> str:
        counts = self.counts
        if counts[JobStatus.CANCELLED]:
            return "Annullato"
        if counts[JobStatus.FAILED] or counts[JobStatus.SKIPPED]:
            return "Con segnalazioni"
        return "Completato"


def default_history_path(config_path: Path | None = None) -> Path:
    return (config_path or default_config_path()).with_name("history.json")


class HistoryRepository:
    def __init__(self, path: Path | None = None, *, limit: int = DEFAULT_HISTORY_LIMIT):
        if limit <= 0:
            raise ValueError("Il limite della cronologia deve essere positivo")
        self.path = path or default_history_path()
        self.limit = limit
        self._lock = threading.Lock()

    def load(self) -> tuple[BatchHistoryRecord, ...]:
        with self._lock:
            return self._load_unlocked()

    def append(self, record: BatchHistoryRecord) -> tuple[BatchHistoryRecord, ...]:
        with self._lock:
            records = (record, *self._load_unlocked())[: self.limit]
            self._save_unlocked(records)
            return records

    def _load_unlocked(self) -> tuple[BatchHistoryRecord, ...]:
        if not self.path.exists():
            return ()
        with self.path.open("r", encoding="utf-8") as stream:
            raw = json.load(stream)
        if not isinstance(raw, dict) or set(raw) != {"version", "records"}:
            raise ValueError("Formato archivio cronologia non valido")
        if raw["version"] != HISTORY_VERSION or not isinstance(raw["records"], list):
            raise ValueError("Versione archivio cronologia non supportata")
        return tuple(BatchHistoryRecord.from_dict(item) for item in raw["records"])

    def _save_unlocked(self, records: tuple[BatchHistoryRecord, ...]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix="history-", suffix=".tmp", dir=self.path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(
                    {
                        "version": HISTORY_VERSION,
                        "records": [record.to_dict() for record in records],
                    },
                    stream,
                    ensure_ascii=False,
                    indent=2,
                )
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
