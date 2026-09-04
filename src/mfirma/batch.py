from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from pathlib import Path

from .errors import FileChangedError, MFirmaError, OutputExistsError
from .models import DocumentCandidate, JobStatus, SignJob
from .output import create_temporary_output, destination_for, publish_temporary
from .provider import SigningProvider


ProgressCallback = Callable[[int, int, SignJob], None]


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
                        continue
                    self._run_one(session, job)
                    if progress:
                        progress(index, len(jobs), job)
        except Exception as exc:
            for index, job in enumerate(jobs, start=1):
                if job.status is JobStatus.PENDING:
                    job.status = JobStatus.FAILED
                    job.error_code = getattr(exc, "code", "SIGNATURE_FAILED")
                    job.message = str(exc)
                    if progress:
                        progress(index, len(jobs), job)
        return jobs

    def _run_one(self, session: object, job: SignJob) -> None:
        temporary: Path | None = None
        try:
            job.status = JobStatus.CHECKING
            stat = job.document.source.stat()
            if (
                stat.st_size != job.document.size
                or stat.st_mtime_ns != job.document.modified_ns
            ):
                raise FileChangedError("Il file è cambiato dopo la selezione")
            temporary = create_temporary_output(job.destination)
            job.status = JobStatus.SIGNING
            session.sign_pdf(job.document.source, temporary)  # type: ignore[attr-defined]
            publish_temporary(temporary, job.destination)
            temporary = None
            job.status = JobStatus.SUCCEEDED
            job.message = str(job.destination)
        except OutputExistsError as exc:
            job.status = JobStatus.SKIPPED
            job.error_code = exc.code
            job.message = str(exc)
        except (MFirmaError, OSError) as exc:
            job.status = JobStatus.FAILED
            job.error_code = getattr(exc, "code", "OUTPUT_WRITE_FAILED")
            job.message = str(exc)
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error_code = "SIGNATURE_FAILED"
            job.message = str(exc)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

