from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from mfirma.history import BatchHistoryRecord, HistoryRepository
from mfirma.models import DocumentCandidate, JobStatus, SignJob


def _job(workdir, name: str, status: JobStatus, *, message: str = "") -> SignJob:
    source = workdir / name
    source.write_bytes(b"%PDF-fake")
    return SignJob(
        DocumentCandidate.from_path(source, "Mario Rossi"),
        workdir / f"{source.stem}_firmato.pdf",
        status=status,
        error_code="SIGNATURE_FAILED" if status is JobStatus.FAILED else None,
        message=message,
    )


def _record(workdir, name: str, status: JobStatus, *, minute: int = 0):
    return BatchHistoryRecord.from_jobs(
        (_job(workdir, name, status),),
        certificate_label="DS user Certificate3",
        created_at=datetime(2026, 9, 6, 13, minute, tzinfo=timezone(timedelta(hours=2))),
    )


def test_history_round_trip_is_atomic_and_excludes_technical_messages(workdir):
    failed = _job(
        workdir,
        "pratica.pdf",
        JobStatus.FAILED,
        message="errore middleware con PIN 1234-segreto",
    )
    record = BatchHistoryRecord.from_jobs(
        (failed,),
        certificate_label="Certificato firma",
        created_at=datetime(2026, 9, 6, 15, 30, tzinfo=timezone.utc),
    )
    repository = HistoryRepository(workdir / "history.json")

    saved = repository.append(record)
    loaded = repository.load()

    assert saved == loaded == (record,)
    payload = (workdir / "history.json").read_text(encoding="utf-8")
    assert "1234-segreto" not in payload
    assert "errore middleware" not in payload
    assert set(json.loads(payload)) == {"version", "records"}
    assert not list(workdir.glob("history-*.tmp"))


def test_history_rejects_non_terminal_jobs_and_naive_timestamps(workdir):
    pending = _job(workdir, "attesa.pdf", JobStatus.PENDING)

    with pytest.raises(ValueError, match="definitivi"):
        BatchHistoryRecord.from_jobs((pending,), certificate_label="Certificato")
    with pytest.raises(ValueError, match="fuso orario"):
        BatchHistoryRecord.from_jobs(
            (_job(workdir, "finito.pdf", JobStatus.SUCCEEDED),),
            certificate_label="Certificato",
            created_at=datetime(2026, 9, 6, 15, 30),
        )


def test_history_keeps_newest_records_up_to_configured_limit(workdir):
    repository = HistoryRepository(workdir / "history.json", limit=2)
    first = _record(workdir, "uno.pdf", JobStatus.SUCCEEDED, minute=1)
    second = _record(workdir, "due.pdf", JobStatus.FAILED, minute=2)
    third = _record(workdir, "tre.pdf", JobStatus.CANCELLED, minute=3)

    repository.append(first)
    repository.append(second)
    records = repository.append(third)

    assert records == (third, second)
    assert [record.outcome for record in records] == [
        "Annullato",
        "Con segnalazioni",
    ]


def test_history_rejects_unknown_schema_without_overwriting_it(workdir):
    path = workdir / "history.json"
    original = '{"version":99,"records":[]}'
    path.write_text(original, encoding="utf-8")
    repository = HistoryRepository(path)

    with pytest.raises(ValueError, match="Versione"):
        repository.load()
    with pytest.raises(ValueError, match="Versione"):
        repository.append(_record(workdir, "nuovo.pdf", JobStatus.SUCCEEDED))

    assert path.read_text(encoding="utf-8") == original
