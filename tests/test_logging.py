from __future__ import annotations

import logging
from contextlib import contextmanager

from mfirma.batch import BatchOrchestrator
from mfirma.logging_setup import configure_logging, shutdown_logging
from mfirma.models import DocumentCandidate, JobStatus


def test_rotating_log_is_utf8_and_bounded(workdir):
    path = workdir / "logs" / "mfirma.log"
    try:
        assert configure_logging(path) == path.resolve()
        logger = logging.getLogger("mfirma.test")
        logger.warning("Anomalia di prova: certificato non disponibile")
        handler = next(
            handler
            for handler in logging.getLogger("mfirma").handlers
            if getattr(handler, "_mfirma_rotating_file_handler", False)
        )
        handler.flush()

        text = path.read_text(encoding="utf-8")
        assert "Anomalia di prova" in text
        assert handler.maxBytes == 1_048_576
        assert handler.backupCount == 5
    finally:
        shutdown_logging()


def test_batch_log_redacts_pin_from_provider_error(workdir):
    path = workdir / "mfirma.log"
    source = workdir / "documento.pdf"
    source.write_bytes(b"%PDF-fake")
    document = DocumentCandidate.from_path(source)

    class FailingProvider:
        @contextmanager
        def open(self, pin):
            raise RuntimeError(f"Errore middleware con valore {pin}")
            yield  # pragma: no cover

    try:
        configure_logging(path)
        jobs = BatchOrchestrator(FailingProvider()).run(
            (document,), pin="pin-segreto-test"
        )
    finally:
        shutdown_logging()

    text = path.read_text(encoding="utf-8")
    assert jobs[0].status is JobStatus.FAILED
    assert "pin-segreto-test" not in text
    assert "[RISERVATO]" in text
    assert "RuntimeError" in text
