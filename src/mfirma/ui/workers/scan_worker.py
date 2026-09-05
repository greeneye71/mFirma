from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from ...scanner import ImportResult, ScanResult, import_candidates, scan_root


class _ScanSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)


class _ScanWorker(QRunnable):
    def __init__(
        self,
        scanner: Callable[..., ScanResult],
        root: Path,
        *,
        recursive: bool,
        stability_seconds: int,
        output_suffix: str,
    ):
        super().__init__()
        self.signals = _ScanSignals()
        self._scanner = scanner
        self._root = root
        self._options = {
            "recursive": recursive,
            "stability_seconds": stability_seconds,
            "output_suffix": output_suffix,
        }

    @Slot()
    def run(self) -> None:
        try:
            result = self._scanner(self._root, **self._options)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        else:
            self.signals.succeeded.emit(result)


class ScanController(QObject):
    scanStarted = Signal()
    scanSucceeded = Signal(object)
    scanFailed = Signal(str)
    busyChanged = Signal(bool)

    def __init__(
        self,
        parent=None,
        *,
        scanner: Callable[..., ScanResult] = scan_root,
        thread_pool: QThreadPool | None = None,
    ):
        super().__init__(parent)
        self._scanner = scanner
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._worker: _ScanWorker | None = None

    @property
    def busy(self) -> bool:
        return self._worker is not None

    def start(
        self,
        root: Path,
        *,
        recursive: bool,
        stability_seconds: int,
        output_suffix: str,
    ) -> bool:
        if self.busy:
            return False
        worker = _ScanWorker(
            self._scanner,
            root,
            recursive=recursive,
            stability_seconds=stability_seconds,
            output_suffix=output_suffix,
        )
        worker.signals.succeeded.connect(self._succeeded)
        worker.signals.failed.connect(self._failed)
        self._worker = worker
        self.scanStarted.emit()
        self.busyChanged.emit(True)
        self._thread_pool.start(worker)
        return True

    @Slot(object)
    def _succeeded(self, result: ScanResult) -> None:
        self._worker = None
        self.busyChanged.emit(False)
        self.scanSucceeded.emit(result)

    @Slot(str)
    def _failed(self, message: str) -> None:
        self._worker = None
        self.busyChanged.emit(False)
        self.scanFailed.emit(message)

    def wait_for_done(self, timeout_ms: int = 3000) -> bool:
        return self._thread_pool.waitForDone(timeout_ms)


class _ImportSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)


class _ImportWorker(QRunnable):
    def __init__(
        self,
        importer: Callable[[tuple[Path, ...]], ImportResult],
        paths: tuple[Path, ...],
    ):
        super().__init__()
        self.signals = _ImportSignals()
        self._importer = importer
        self._paths = paths

    @Slot()
    def run(self) -> None:
        try:
            result = self._importer(self._paths)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        else:
            self.signals.succeeded.emit(result)


class FileImportController(QObject):
    importSucceeded = Signal(object)
    importFailed = Signal(str)
    busyChanged = Signal(bool)

    def __init__(
        self,
        parent=None,
        *,
        importer: Callable[[tuple[Path, ...]], ImportResult] = import_candidates,
        thread_pool: QThreadPool | None = None,
    ):
        super().__init__(parent)
        self._importer = importer
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._worker: _ImportWorker | None = None

    @property
    def busy(self) -> bool:
        return self._worker is not None

    def start(self, paths: tuple[Path, ...]) -> bool:
        if self.busy or not paths:
            return False
        worker = _ImportWorker(self._importer, paths)
        worker.signals.succeeded.connect(self._succeeded)
        worker.signals.failed.connect(self._failed)
        self._worker = worker
        self.busyChanged.emit(True)
        self._thread_pool.start(worker)
        return True

    @Slot(object)
    def _succeeded(self, result: ImportResult) -> None:
        self._worker = None
        self.busyChanged.emit(False)
        self.importSucceeded.emit(result)

    @Slot(str)
    def _failed(self, message: str) -> None:
        self._worker = None
        self.busyChanged.emit(False)
        self.importFailed.emit(message)

    def wait_for_done(self, timeout_ms: int = 3000) -> bool:
        return self._thread_pool.waitForDone(timeout_ms)
