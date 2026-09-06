from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import threading
import uuid

import pytest

from mfirma.batch import BatchOrchestrator
from mfirma.models import DocumentCandidate, JobStatus
from mfirma.signature_register import JsonlSignatureRegister, SigningIdentity


class Provider:
    def __init__(self):
        self.calls = 0

    @contextmanager
    def open(self, pin):
        self.calls += 1
        yield self

    def sign_pdf(self, source, output, **kwargs):
        if source.stem == "errore":
            raise RuntimeError("errore PIN-secret")
        output.write_bytes(source.read_bytes() + b"SIGNED")


def document(workdir, name="documento.pdf"):
    source = workdir / name
    source.write_bytes(b"originale")
    return DocumentCandidate.from_path(source)


def records(register):
    return [json.loads(line) for line in register.path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("action", ["keep", "overwrite", "delete"])
def test_register_tracks_actual_signed_file_and_identity(workdir, action):
    register = JsonlSignatureRegister(workdir / "signatures.jsonl")
    identity = SigningIdentity(
        signer_name="Mario Rossi", token_label="Card", token_serial="4142",
        certificate_label="Firma", certificate_id="01", certificate_serial="12345",
        certificate_subject="CN=Mario Rossi,O=Azienda", certificate_issuer="CN=CA",
        certificate_sha256="a" * 64,
    )
    candidate = document(workdir)
    job, = BatchOrchestrator(
        Provider(), register=register, signing_identity=identity, mode="manual", source_action=action,
    ).run([candidate], pin="PIN-secret")
    record, = records(register)
    assert record["signer_name"] == "Mario Rossi"
    assert record["token_serial"] == "4142"
    assert record["certificate_serial"] == "12345"
    assert record["certificate_sha256"] == "a" * 64
    assert record["mode"] == "manual"
    assert record["signature_saved"] is True
    assert record["output_sha256"] == hashlib.sha256(job.destination.read_bytes()).hexdigest()
    assert record["signed_at_utc"].endswith("+00:00")
    assert record["completed_at_utc"].endswith("+00:00")
    assert record["operation_id"] == job.operation_id
    assert record["batch_id"] == job.batch_id
    uuid.UUID(record["operation_id"])
    uuid.UUID(record["workstation_id"])
    assert "PIN-secret" not in register.path.read_text()


def test_register_writes_each_result_before_next_file_and_keeps_failures(workdir):
    register = JsonlSignatureRegister(workdir / "signatures.jsonl")
    documents = [document(workdir, "primo.pdf"), document(workdir, "errore.pdf"), document(workdir, "ultimo.pdf")]
    observed = []
    jobs = BatchOrchestrator(Provider(), register=register).run(
        documents, pin="PIN-secret", progress=lambda *_: observed.append(len(records(register))),
    )
    assert observed == [1, 2, 3]
    saved = records(register)
    assert [row["signature_saved"] for row in saved] == [True, False, True]
    assert saved[1]["error_code"] == "SIGNATURE_FAILED"
    assert saved[1]["output_sha256"] is None
    assert len({row["operation_id"] for row in saved}) == 3
    assert len({job.batch_id for job in jobs}) == 1
    assert "PIN-secret" not in register.path.read_text()


def test_register_reopens_same_station_and_does_not_truncate_at_100(workdir):
    path = workdir / "signatures.jsonl"
    first = JsonlSignatureRegister(path)
    first.prepare()
    for number in range(105):
        first.append({"operation_id": str(uuid.uuid4()), "number": number})
    second = JsonlSignatureRegister(path)
    second.prepare()
    second.append({"operation_id": str(uuid.uuid4()), "number": 105})
    saved = records(second)
    assert len(saved) == 106
    assert len({row["workstation_id"] for row in saved}) == 1


def test_incomplete_register_is_preserved_and_prevents_signing(workdir):
    path = workdir / "signatures.jsonl"
    path.write_bytes(b'{"interrupted":')
    provider = Provider()
    candidate = document(workdir)
    job, = BatchOrchestrator(provider, register=JsonlSignatureRegister(path)).run([candidate], pin=None)
    assert provider.calls == 0
    assert job.status is JobStatus.FAILED
    assert job.register_error
    assert candidate.source.read_bytes() == b"originale"
    assert path.read_bytes() == b'{"interrupted":'


def test_register_write_failure_preserves_signed_file_and_stops_rest(workdir, monkeypatch):
    register = JsonlSignatureRegister(workdir / "signatures.jsonl")

    def fail(record):
        raise OSError("disco pieno")

    monkeypatch.setattr(register, "append", fail)
    jobs = BatchOrchestrator(Provider(), register=register).run(
        [document(workdir, "primo.pdf"), document(workdir, "secondo.pdf")], pin=None,
    )
    assert jobs[0].status is JobStatus.SUCCEEDED
    assert jobs[0].register_error
    assert jobs[0].destination.exists()
    assert jobs[1].status is JobStatus.CANCELLED
    assert not jobs[1].destination.exists()


def test_delete_error_is_recorded_as_saved_signature(workdir, monkeypatch):
    candidate = document(workdir)
    register = JsonlSignatureRegister(workdir / "signatures.jsonl")
    original_unlink = Path.unlink

    def deny_source(path, *args, **kwargs):
        if path == candidate.source:
            raise PermissionError("occupato")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", deny_source)
    BatchOrchestrator(Provider(), register=register, source_action="delete").run([candidate], pin=None)
    record, = records(register)
    assert record["signature_saved"] is True
    assert record["error_code"] == "SOURCE_DELETE_FAILED"
    assert record["output_sha256"]


def test_cancelled_documents_are_recorded_without_signatures(workdir):
    cancellation = threading.Event()
    cancellation.set()
    register = JsonlSignatureRegister(workdir / "signatures.jsonl")
    BatchOrchestrator(Provider(), register=register).run([document(workdir)], pin=None, cancel=cancellation)
    record, = records(register)
    assert record["status"] == JobStatus.CANCELLED.value
    assert record["signature_saved"] is False
    assert record["signed_at_utc"] is None
