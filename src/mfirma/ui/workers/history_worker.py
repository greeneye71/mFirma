from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from ...history import BatchHistoryRecord, HistoryRepository


class _HistorySignals(QObject):
    succeeded = Signal(str, object)
    failed = Signal(str, str)


class _HistoryWorker(QRunnable):
    def __init__(self, operation: str, callback: Callable[[], object]):
        super().__init__()
        self.signals = _HistorySignals()
        self._operation = operation
        self._callback = callback

    @Slot()
    def run(self) -> None:
        try:
            result = self._callback()
        except Exception as exc:
            self.signals.failed.emit(
                self._operation, f"{type(exc).__name__}: {exc}"
            )
        else:
            self.signals.succeeded.emit(self._operation, result)


class HistoryController(QObject):
    historyChanged = Signal(object)
    operationFailed = Signal(str, str)
    busyChanged = Signal(bool)

    def __init__(
        self,
        repository: HistoryRepository,
        parent=None,
        *,
        thread_pool: QThreadPool | None = None,
    ):
        super().__init__(parent)
        self.repository = repository
        self._thread_pool = thread_pool or QThreadPool(self)
        if thread_pool is None:
            self._thread_pool.setMaxThreadCount(1)
        self._active = 0
        self._workers: set[_HistoryWorker] = set()

    @property
    def busy(self) -> bool:
        return self._active > 0

    def load(self) -> None:
        self._start("load", self.repository.load)

    def append(self, record: BatchHistoryRecord) -> None:
        self._start("append", lambda: self.repository.append(record))

    def _start(self, operation: str, callback: Callable[[], object]) -> None:
        worker = _HistoryWorker(operation, callback)
        worker.signals.succeeded.connect(
            lambda current_operation, result, current_worker=worker: self._succeeded(
                current_worker, current_operation, result
            )
        )
        worker.signals.failed.connect(
            lambda current_operation, message, current_worker=worker: self._failed(
                current_worker, current_operation, message
            )
        )
        self._workers.add(worker)
        was_busy = self.busy
        self._active += 1
        if not was_busy:
            self.busyChanged.emit(True)
        self._thread_pool.start(worker)

    def _succeeded(
        self, worker: _HistoryWorker, operation: str, records: object
    ) -> None:
        self._finish(worker)
        self.historyChanged.emit(records)

    def _failed(
        self, worker: _HistoryWorker, operation: str, message: str
    ) -> None:
        self._finish(worker)
        self.operationFailed.emit(operation, message)

    def _finish(self, worker: _HistoryWorker) -> None:
        self._workers.discard(worker)
        self._active -= 1
        if not self.busy:
            self.busyChanged.emit(False)

    def wait_for_done(self, timeout_ms: int = 3000) -> bool:
        return self._thread_pool.waitForDone(timeout_ms)
