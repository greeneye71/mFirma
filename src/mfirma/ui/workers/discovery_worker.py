from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from ...discovery import DiscoveryResult, discover_pkcs11_modules


class DiscoveryOperation(StrEnum):
    DISCOVER = "discover"
    INSPECT = "inspect"


@dataclass(frozen=True, slots=True)
class DiscoveryOutcome:
    operation: DiscoveryOperation
    result: DiscoveryResult
    requested_path: Path | None = None
    show_certificates: bool = False


class _DiscoverySignals(QObject):
    succeeded = Signal(object)
    failed = Signal(object, str)


class _DiscoveryWorker(QRunnable):
    def __init__(
        self,
        discoverer: Callable[..., DiscoveryResult],
        operation: DiscoveryOperation,
        *,
        search_roots: Iterable[Path] | None,
        extra_paths: tuple[Path, ...],
        probe_timeout: float,
        requested_path: Path | None,
        show_certificates: bool,
    ):
        super().__init__()
        self.signals = _DiscoverySignals()
        self._discoverer = discoverer
        self._operation = operation
        self._options = {
            "search_roots": search_roots,
            "extra_paths": extra_paths,
            "probe_timeout": probe_timeout,
        }
        self._requested_path = requested_path
        self._show_certificates = show_certificates

    @Slot()
    def run(self) -> None:
        try:
            result = self._discoverer(**self._options)
        except Exception as exc:
            self.signals.failed.emit(self._operation, str(exc))
            return
        self.signals.succeeded.emit(
            DiscoveryOutcome(
                operation=self._operation,
                result=result,
                requested_path=self._requested_path,
                show_certificates=self._show_certificates,
            )
        )


class DiscoveryController(QObject):
    operationStarted = Signal(object)
    operationSucceeded = Signal(object)
    operationFailed = Signal(object, str)
    busyChanged = Signal(bool)

    def __init__(
        self,
        parent=None,
        *,
        discoverer: Callable[..., DiscoveryResult] = discover_pkcs11_modules,
        thread_pool: QThreadPool | None = None,
    ):
        super().__init__(parent)
        self._discoverer = discoverer
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._worker: _DiscoveryWorker | None = None

    @property
    def busy(self) -> bool:
        return self._worker is not None

    def discover(self, extra_paths: tuple[Path, ...] = ()) -> bool:
        return self._start(
            DiscoveryOperation.DISCOVER,
            search_roots=None,
            extra_paths=extra_paths,
            probe_timeout=6.0,
        )

    def inspect(self, path: Path, *, show_certificates: bool = False) -> bool:
        return self._start(
            DiscoveryOperation.INSPECT,
            search_roots=(),
            extra_paths=(path,),
            probe_timeout=8.0,
            requested_path=path,
            show_certificates=show_certificates,
        )

    def _start(
        self,
        operation: DiscoveryOperation,
        *,
        search_roots: Iterable[Path] | None,
        extra_paths: tuple[Path, ...],
        probe_timeout: float,
        requested_path: Path | None = None,
        show_certificates: bool = False,
    ) -> bool:
        if self.busy:
            return False
        worker = _DiscoveryWorker(
            self._discoverer,
            operation,
            search_roots=search_roots,
            extra_paths=extra_paths,
            probe_timeout=probe_timeout,
            requested_path=requested_path,
            show_certificates=show_certificates,
        )
        worker.signals.succeeded.connect(self._succeeded)
        worker.signals.failed.connect(self._failed)
        self._worker = worker
        self.operationStarted.emit(operation)
        self.busyChanged.emit(True)
        self._thread_pool.start(worker)
        return True

    @Slot(object)
    def _succeeded(self, outcome: DiscoveryOutcome) -> None:
        self._worker = None
        self.busyChanged.emit(False)
        self.operationSucceeded.emit(outcome)

    @Slot(object, str)
    def _failed(self, operation: DiscoveryOperation, message: str) -> None:
        self._worker = None
        self.busyChanged.emit(False)
        self.operationFailed.emit(operation, message)

    def wait_for_done(self, timeout_ms: int = 3000) -> bool:
        return self._thread_pool.waitForDone(timeout_ms)
