from __future__ import annotations

import logging
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
LOGGER = logging.getLogger(__name__)


def _redact_secret(message: str, secret: str | None) -> str:
    if secret:
        return message.replace(secret, "[RISERVATO]")
    return message


class BatchOrchestrator:
    def __init__(
        self, provider: SigningProvider, output_suffix: str = "_firmato", *,
        output_directory: Path | None = None, source_action: str = "keep",
    ):
        if source_action not in {"keep", "overwrite", "delete"}:
            raise ValueError("Azione sul file originale non valida")
        self.provider = provider
        self.output_suffix = output_suffix
        self.output_directory = output_directory
        self.source_action = source_action

    def build_jobs(self, documents: Iterable[DocumentCandidate]) -> list[SignJob]:
        unique: dict[str, DocumentCandidate] = {}
        for document in documents:
            unique[str(document.source.resolve()).casefold()] = document
        return [
            SignJob(document, destination_for(
                document.source, self.output_suffix,
                directory=self.output_directory,
                overwrite_source=self.source_action == "overwrite",
            ))
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
        LOGGER.info("Avvio batch: documenti=%d", len(jobs))

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
            safe_message = _redact_secret(str(exc), pin)
            LOGGER.error(
                "Apertura sessione di firma non riuscita: tipo=%s codice=%s dettaglio=%s",
                type(exc).__name__,
                getattr(exc, "code", "SIGNATURE_FAILED"),
                safe_message,
            )
            for index, job in enumerate(jobs, start=1):
                if job.status is JobStatus.PENDING:
                    job.status = JobStatus.FAILED
                    job.error_code = getattr(exc, "code", "SIGNATURE_FAILED")
                    job.message = safe_message
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
        LOGGER.info(
            "Fine batch: riusciti=%d errori=%d saltati=%d annullati=%d",
            sum(job.status is JobStatus.SUCCEEDED for job in jobs),
            sum(job.status is JobStatus.FAILED for job in jobs),
            sum(job.status is JobStatus.SKIPPED for job in jobs),
            sum(job.status is JobStatus.CANCELLED for job in jobs),
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
            temporary = create_temporary_output(
                job.destination, overwrite=self.source_action == "overwrite",
            )
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
            if self.source_action != "keep":
                self._check_source_unchanged(job)
            publish_temporary(
                temporary, job.destination, overwrite=self.source_action == "overwrite",
            )
            temporary = None
            if self.source_action == "delete":
                try:
                    self._check_source_unchanged(job)
                    job.document.source.unlink()
                except (OSError, FileChangedError) as exc:
                    job.status = JobStatus.FAILED
                    job.error_code = "SOURCE_DELETE_FAILED"
                    job.message = _redact_secret(
                        f"File firmato salvato in {job.destination}; originale non eliminato: {exc}",
                        secret,
                    )
                    self._log_job_problem(job)
                    return
            job.status = JobStatus.SUCCEEDED
            job.message = str(job.destination)
        except OutputExistsError as exc:
            job.status = JobStatus.SKIPPED
            job.error_code = exc.code
            job.message = _redact_secret(str(exc), secret)
            self._log_job_problem(job)
        except (MFirmaError, OSError) as exc:
            job.status = JobStatus.FAILED
            job.error_code = getattr(exc, "code", "OUTPUT_WRITE_FAILED")
            job.message = _redact_secret(str(exc), secret)
            self._log_job_problem(job)
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error_code = "SIGNATURE_FAILED"
            job.message = _redact_secret(str(exc), secret)
            self._log_job_problem(job)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @staticmethod
    def _check_source_unchanged(job: SignJob) -> None:
        stat = job.document.source.stat()
        if (stat.st_size != job.document.size
                or stat.st_mtime_ns != job.document.modified_ns):
            raise FileChangedError("Il file è cambiato durante la firma")

    @staticmethod
    def _log_job_problem(job: SignJob) -> None:
        log = LOGGER.warning if job.status is JobStatus.SKIPPED else LOGGER.error
        log(
            "Documento non completato: file=%s stato=%s codice=%s dettaglio=%s",
            job.document.source.name,
            job.status,
            job.error_code or "UNKNOWN",
            job.message,
        )
