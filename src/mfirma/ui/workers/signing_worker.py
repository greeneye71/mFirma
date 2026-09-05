from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from ...batch import BatchOrchestrator
from ...models import DocumentCandidate, SignaturePositionPlan


class _SigningSignals(QObject):
    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)


class _SigningWorker(QRunnable):
    def __init__(
        self,
        orchestrator: BatchOrchestrator,
        documents: tuple[DocumentCandidate, ...],
        pin: str | None,
        cancel_event: threading.Event,
        position_plan: SignaturePositionPlan,
    ):
        super().__init__()
        self.signals = _SigningSignals()
        self._orchestrator = orchestrator
        self._documents = documents
        self._pin = pin
        self._cancel_event = cancel_event
        self._position_plan = position_plan

    @Slot()
    def run(self) -> None:
        secret = self._pin
        self._pin = None
        try:
            jobs = self._orchestrator.run(
                self._documents,
                pin=secret,
                cancel=self._cancel_event,
                events=self.signals.progress.emit,
                placements=self._position_plan.placements,
                normalized_rect=self._position_plan.shared_rect,
            )
        except Exception as exc:
            message = str(exc)
            if secret:
                message = message.replace(secret, "[RISERVATO]")
            self.signals.failed.emit(
                f"BATCH_WORKER_FAILED: {type(exc).__name__}: {message}"
            )
        else:
            self.signals.finished.emit(jobs)
        finally:
            secret = None


class SigningController(QObject):
    batchStarted = Signal(int)
    progressChanged = Signal(object)
    batchFinished = Signal(object)
    batchFailed = Signal(str)
    busyChanged = Signal(bool)
    cancellationChanged = Signal(bool)

    def __init__(self, parent=None, *, thread_pool: QThreadPool | None = None):
        super().__init__(parent)
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._worker: _SigningWorker | None = None
        self._cancel_event: threading.Event | None = None

    @property
    def busy(self) -> bool:
        return self._worker is not None

    def start(
        self,
        orchestrator: BatchOrchestrator,
        documents: tuple[DocumentCandidate, ...],
        *,
        pin: str | None,
        position_plan: SignaturePositionPlan,
    ) -> bool:
        if self.busy or not documents:
            return False
        cancellation = threading.Event()
        worker = _SigningWorker(
            orchestrator,
            documents,
            pin,
            cancellation,
            position_plan,
        )
        worker.signals.progress.connect(self.progressChanged)
        worker.signals.finished.connect(self._finished)
        worker.signals.failed.connect(self._failed)
        self._worker = worker
        self._cancel_event = cancellation
        self.batchStarted.emit(len(documents))
        self.busyChanged.emit(True)
        self.cancellationChanged.emit(False)
        self._thread_pool.start(worker)
        return True

    @Slot()
    def request_cancel(self) -> None:
        if self._cancel_event is not None and not self._cancel_event.is_set():
            self._cancel_event.set()
            self.cancellationChanged.emit(True)

    @Slot(object)
    def _finished(self, jobs) -> None:
        self._worker = None
        self._cancel_event = None
        self.busyChanged.emit(False)
        self.batchFinished.emit(jobs)

    @Slot(str)
    def _failed(self, message: str) -> None:
        self._worker = None
        self._cancel_event = None
        self.busyChanged.emit(False)
        self.batchFailed.emit(message)

    def wait_for_done(self, timeout_ms: int = 3000) -> bool:
        return self._thread_pool.waitForDone(timeout_ms)
