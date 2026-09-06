from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from mfirma.batch import BatchOrchestrator
from mfirma.models import (
    BatchPhase,
    DocumentCandidate,
    JobStatus,
    NormalizedDisplayRect,
    SignaturePlacement,
)


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


class EventSession:
    def __init__(self):
        self.calls = []

    def sign_pdf(
        self,
        source,
        temporary_output,
        *,
        placement=None,
        normalized_rect=None,
        phase_callback=None,
    ):
        self.calls.append((source, placement, normalized_rect))
        temporary_output.write_bytes(source.read_bytes() + b"\nSIGNED")
        phase_callback("verifying")


class EventProvider:
    def __init__(self):
        self.session = EventSession()

    @contextmanager
    def open(self, pin):
        yield self.session


def test_batch_emits_structured_phases_and_forwards_position(workdir: Path):
    source = workdir / "posizione.pdf"
    source.write_bytes(b"%PDF-test")
    document = candidate(source)
    placement = SignaturePlacement(0, 10, 20, 190, 88)
    events = []
    provider = EventProvider()

    jobs = BatchOrchestrator(provider).run(
        [document],
        pin=None,
        placements={str(source.resolve()).casefold(): placement},
        normalized_rect=NormalizedDisplayRect(0.1, 0.1, 0.3, 0.2),
        events=events.append,
    )

    assert jobs[0].status is JobStatus.SUCCEEDED
    assert [event.phase for event in events] == [
        BatchPhase.CHECKING,
        BatchPhase.SIGNING,
        BatchPhase.VERIFYING,
        BatchPhase.PUBLISHING,
        BatchPhase.COMPLETED,
    ]
    assert [event.completed for event in events] == [0, 0, 0, 0, 1]
    assert provider.session.calls == [(source.resolve(), placement, None)]


class FailingProvider:
    @contextmanager
    def open(self, pin):
        raise RuntimeError(f"accesso negato per {pin}")
        yield


def test_batch_redacts_pin_from_jobs_and_progress_events(workdir: Path):
    source = workdir / "riservato.pdf"
    source.write_bytes(b"%PDF-test")
    events = []

    jobs = BatchOrchestrator(FailingProvider()).run(
        [candidate(source)],
        pin="9876-segreto",
        events=events.append,
    )

    assert jobs[0].status is JobStatus.FAILED
    assert "9876-segreto" not in jobs[0].message
    assert "[RISERVATO]" in jobs[0].message
    assert all("9876-segreto" not in event.job.message for event in events)


@pytest.mark.parametrize("action", ["keep", "overwrite", "delete"])
def test_output_policies(workdir, action):
    source = workdir / "documento.pdf"
    source.write_bytes(b"originale")
    destination_dir = workdir / "firmati"
    job, = BatchOrchestrator(
        FakeProvider(), output_directory=destination_dir, source_action=action,
    ).run([candidate(source)], pin=None)
    assert job.status is JobStatus.SUCCEEDED
    assert job.destination.read_bytes() == b"originale\nTEST-SIGNATURE"
    if action == "overwrite":
        assert job.destination == source.resolve()
        assert not destination_dir.exists()
    else:
        assert job.destination.parent == destination_dir.resolve()
        assert source.exists() == (action == "keep")
        if action == "keep":
            assert source.read_bytes() == b"originale"


@pytest.mark.parametrize("action", ["overwrite", "delete"])
def test_failed_signature_preserves_original(workdir, action):
    source = workdir / "guasto.pdf"
    source.write_bytes(b"originale")
    job, = BatchOrchestrator(FakeProvider(), source_action=action).run(
        [candidate(source)], pin=None,
    )
    assert job.status is JobStatus.FAILED
    assert source.read_bytes() == b"originale"
    assert not list(workdir.glob("*.tmp"))


def test_collisions_in_shared_directory_preserve_second_source(workdir):
    first = workdir / "uno" / "documento.pdf"
    second = workdir / "due" / "documento.pdf"
    for source in (first, second):
        source.parent.mkdir()
        source.write_bytes(source.parent.name.encode())
    jobs = BatchOrchestrator(
        FakeProvider(), output_directory=workdir / "firmati", source_action="delete",
    ).run([candidate(first), candidate(second)], pin=None)
    assert [job.status for job in jobs] == [JobStatus.SUCCEEDED, JobStatus.SKIPPED]
    assert not first.exists()
    assert second.read_bytes() == b"due"
    assert jobs[0].destination.read_bytes() == b"uno\nTEST-SIGNATURE"


@pytest.mark.parametrize("action", ["overwrite", "delete"])
def test_source_changed_during_signing_is_preserved(workdir, monkeypatch, action):
    source = workdir / "documento.pdf"
    source.write_bytes(b"originale")

    def sign_and_change(self, source, temporary_output):
        temporary_output.write_bytes(b"firmato")
        source.write_bytes(b"modificato da altro programma")

    monkeypatch.setattr(FakeSession, "sign_pdf", sign_and_change)
    job, = BatchOrchestrator(FakeProvider(), source_action=action).run(
        [candidate(source)], pin=None,
    )
    assert job.error_code == "FILE_CHANGED"
    assert source.read_bytes() == b"modificato da altro programma"


def test_delete_failure_reports_saved_copy(workdir, monkeypatch):
    source = workdir / "documento.pdf"
    source.write_bytes(b"originale")
    original_unlink = Path.unlink

    def deny_source_delete(path, *args, **kwargs):
        if path == source.resolve():
            raise PermissionError("File occupato")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", deny_source_delete)
    job, = BatchOrchestrator(FakeProvider(), source_action="delete").run(
        [candidate(source)], pin=None,
    )
    assert job.error_code == "SOURCE_DELETE_FAILED"
    assert job.destination.read_bytes().endswith(b"TEST-SIGNATURE")
    assert source.read_bytes() == b"originale"


def test_replace_failure_preserves_original(workdir, monkeypatch):
    source = workdir / "documento.pdf"
    source.write_bytes(b"originale")

    def deny_replace(*args):
        raise PermissionError("File occupato")

    monkeypatch.setattr("mfirma.output.os.replace", deny_replace)
    job, = BatchOrchestrator(FakeProvider(), source_action="overwrite").run(
        [candidate(source)], pin=None,
    )
    assert job.status is JobStatus.FAILED
    assert source.read_bytes() == b"originale"
    assert not list(workdir.glob("*.tmp"))
