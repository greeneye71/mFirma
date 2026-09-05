from __future__ import annotations

import threading
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

from .errors import FileChangedError, MFirmaError, OutputExistsError
from .models import (
    BatchPhase,
    BatchProgress,
    DocumentCandidate,
    JobStatus,
    NormalizedDisplayRect,
    SignJob,
    SignaturePlacement,
)
from .output import create_temporary_output, destination_for, publish_temporary
from .provider import SigningProvider


ProgressCallback = Callable[[int, int, SignJob], None]
EventCallback = Callable[[BatchProgress], None]


def _redact_secret(message: str, secret: str | None) -> str:
    if secret:
        return message.replace(secret, "[RISERVATO]")
    return message


class BatchOrchestrator:
    def __init__(self, provider: SigningProvider, output_suffix: str = "_firmato"):
        self.provider = provider
        self.output_suffix = output_suffix

    def build_jobs(self, documents: Iterable[DocumentCandidate]) -> list[SignJob]:
        unique: dict[str, DocumentCandidate] = {}
        for document in documents:
            unique[str(document.source.resolve()).casefold()] = document
        return [
            SignJob(document, destination_for(document.source, self.output_suffix))
            for document in unique.values()
        ]

    def run(
        self,
        documents: Iterable[DocumentCandidate],
        *,
        pin: str | None,
        cancel: threading.Event | None = None,
        progress: ProgressCallback | None = None,
        events: EventCallback | None = None,
        placements: Mapping[str, SignaturePlacement] | None = None,
        normalized_rect: NormalizedDisplayRect | None = None,
    ) -> list[SignJob]:
        jobs = self.build_jobs(documents)
        cancellation = cancel or threading.Event()

        try:
            with self.provider.open(pin) as session:
                for index, job in enumerate(jobs, start=1):
                    if cancellation.is_set():
                        job.status = JobStatus.CANCELLED
                        job.message = "Non iniziato"
                        if progress:
                            progress(index, len(jobs), job)
                        if events:
                            events(
                                BatchProgress(
                                    index,
                                    len(jobs),
                                    index,
                                    BatchPhase.COMPLETED,
                                    job,
                                )
                            )
                        continue
                    key = str(job.document.source.resolve()).casefold()
                    placement = placements.get(key) if placements else None
                    self._run_one(
                        session,
                        job,
                        index=index,
                        total=len(jobs),
                        events=events,
                        placement=placement,
                        normalized_rect=normalized_rect if placement is None else None,
                        secret=pin,
                    )
                    if progress:
                        progress(index, len(jobs), job)
                    if events:
                        events(
                            BatchProgress(
                                index,
                                len(jobs),
                                index,
                                BatchPhase.COMPLETED,
                                job,
                            )
                        )
        except Exception as exc:
            for index, job in enumerate(jobs, start=1):
                if job.status is JobStatus.PENDING:
                    job.status = JobStatus.FAILED
                    job.error_code = getattr(exc, "code", "SIGNATURE_FAILED")
                    job.message = _redact_secret(str(exc), pin)
                    if progress:
                        progress(index, len(jobs), job)
                    if events:
                        events(
                            BatchProgress(
                                index,
                                len(jobs),
                                index,
                                BatchPhase.COMPLETED,
                                job,
                            )
                        )
        return jobs

    def _run_one(
        self,
        session: object,
        job: SignJob,
        *,
        index: int,
        total: int,
        events: EventCallback | None,
        placement: SignaturePlacement | None,
        normalized_rect: NormalizedDisplayRect | None,
        secret: str | None,
    ) -> None:
        temporary: Path | None = None

        def emit(phase: BatchPhase) -> None:
            if events:
                events(BatchProgress(index, total, index - 1, phase, job))

        try:
            job.status = JobStatus.CHECKING
            emit(BatchPhase.CHECKING)
            stat = job.document.source.stat()
            if (
                stat.st_size != job.document.size
                or stat.st_mtime_ns != job.document.modified_ns
            ):
                raise FileChangedError("Il file è cambiato dopo la selezione")
            temporary = create_temporary_output(job.destination)
            job.status = JobStatus.SIGNING
            emit(BatchPhase.SIGNING)
            if events or placement is not None or normalized_rect is not None:
                session.sign_pdf(  # type: ignore[attr-defined]
                    job.document.source,
                    temporary,
                    placement=placement,
                    normalized_rect=normalized_rect,
                    phase_callback=lambda _phase: emit(BatchPhase.VERIFYING),
                )
            else:
                session.sign_pdf(  # type: ignore[attr-defined]
                    job.document.source, temporary
                )
            emit(BatchPhase.PUBLISHING)
            publish_temporary(temporary, job.destination)
            temporary = None
            job.status = JobStatus.SUCCEEDED
            job.message = str(job.destination)
        except OutputExistsError as exc:
            job.status = JobStatus.SKIPPED
            job.error_code = exc.code
            job.message = _redact_secret(str(exc), secret)
        except (MFirmaError, OSError) as exc:
            job.status = JobStatus.FAILED
            job.error_code = getattr(exc, "code", "OUTPUT_WRITE_FAILED")
            job.message = _redact_secret(str(exc), secret)
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error_code = "SIGNATURE_FAILED"
            job.message = _redact_secret(str(exc), secret)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
