"""Registro per documento, indipendente dalla cronologia e dal futuro trasporto remoto."""
from __future__ import annotations

import json
import os
import socket
import threading
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from .models import SignJob


@dataclass(frozen=True, slots=True)
class SigningIdentity:
    signer_name: str = ""
    token_label: str = ""
    token_serial: str = ""
    certificate_label: str = ""
    certificate_id: str = ""
    certificate_serial: str = ""
    certificate_subject: str = ""
    certificate_issuer: str = ""
    certificate_sha256: str = ""


class SignatureRegister(Protocol):
    def prepare(self) -> None: ...
    def append(self, record: dict) -> None: ...


def record_for(job: SignJob, identity: SigningIdentity, *, mode: str, source_action: str) -> dict:
    return {
        "schema_version": 1,
        "operation_id": job.operation_id,
        "batch_id": job.batch_id,
        "completed_at_utc": job.completed_at,
        "signed_at_utc": job.signed_at or None,
        "mode": mode,
        "file_name": job.document.source.name,
        "source_path": str(job.document.source),
        "output_name": job.destination.name,
        "output_path": str(job.destination),
        "output_sha256": job.output_sha256 if job.signature_saved else None,
        "signature_saved": job.signature_saved,
        "status": job.status.value,
        "error_code": job.error_code,
        "source_action": source_action,
        **asdict(identity),
    }


class JsonlSignatureRegister:
    # L'applicazione ha una sola istanza per utente; il lock protegge i worker.
    _lock = threading.Lock()

    def __init__(self, path: Path):
        self.path = path
        self.station_path = path.with_name("workstation.json")
        self._station: dict[str, str] | None = None

    def _load_station(self) -> dict[str, str]:
        if self.station_path.exists():
            station = json.loads(self.station_path.read_text(encoding="utf-8"))
            uuid.UUID(station["id"])
            if not isinstance(station["name"], str):
                raise ValueError("Identità postazione non valida")
            return station
        station = {"id": str(uuid.uuid4()), "name": socket.gethostname()}
        # Creazione esclusiva: non sovrascrive un'identità già esistente.
        with self.station_path.open("x", encoding="utf-8") as stream:
            json.dump(station, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        return station

    def prepare(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._station = self._load_station()
            with self.path.open("a+b") as stream:
                self._check_tail(stream)
                stream.flush()
                os.fsync(stream.fileno())

    @staticmethod
    def _check_tail(stream) -> None:
        stream.seek(0, os.SEEK_END)
        if stream.tell():
            stream.seek(-1, os.SEEK_END)
            if stream.read(1) != b"\n":
                raise ValueError("Registro incompleto: conservare il file e ripristinarlo prima di firmare")
        stream.seek(0, os.SEEK_END)

    def append(self, record: dict) -> None:
        if self._station is None:
            self.prepare()
        payload = {**record, "workstation_id": self._station["id"], "workstation_name": self._station["name"]}
        data = (json.dumps(payload, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        with self._lock, self.path.open("a+b") as stream:
            self._check_tail(stream)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
