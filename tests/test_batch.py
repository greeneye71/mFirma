from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from mfirma.batch import BatchOrchestrator
from mfirma.models import DocumentCandidate, JobStatus


class FakeSession:
    def sign_pdf(self, source: Path, temporary_output: Path) -> None:
        if source.name == "guasto.pdf":
            raise RuntimeError("errore simulato")
        temporary_output.write_bytes(source.read_bytes() + b"\nTEST-SIGNATURE")


class FakeProvider:
    def __init__(self):
        self.open_count = 0

    @contextmanager
    def open(self, pin):
        self.open_count += 1
        yield FakeSession()


def candidate(path: Path) -> DocumentCandidate:
    return DocumentCandidate.from_path(path)


def test_batch_uses_one_session_and_continues_after_file_error(workdir: Path):
    first = workdir / "uno.pdf"
    broken = workdir / "guasto.pdf"
    third = workdir / "tre.pdf"
    for path in (first, broken, third):
        path.write_bytes(b"%PDF-test")
    provider = FakeProvider()
    orchestrator = BatchOrchestrator(provider)

    jobs = orchestrator.run([candidate(first), candidate(broken), candidate(third)], pin="x")

    assert provider.open_count == 1
    assert [job.status for job in jobs] == [
        JobStatus.SUCCEEDED,
        JobStatus.FAILED,
        JobStatus.SUCCEEDED,
    ]
    assert first.with_name("uno_firmato.pdf").exists()
    assert not broken.with_name("guasto_firmato.pdf").exists()
    assert third.with_name("tre_firmato.pdf").exists()


def test_existing_output_is_skipped_without_overwrite(workdir: Path):
    source = workdir / "uno.pdf"
    output = workdir / "uno_firmato.pdf"
    source.write_bytes(b"source")
    output.write_bytes(b"keep")
    jobs = BatchOrchestrator(FakeProvider()).run([candidate(source)], pin=None)
    assert jobs[0].status is JobStatus.SKIPPED
    assert output.read_bytes() == b"keep"
