from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox
from qfluentwidgets import FluentIcon, MSFluentWindow

from ..config import AppConfig, ConfigRepository
from ..scanner import ScanResult, candidates_from_paths
from .pages.history_page import HistoryPage
from .pages.queue_page import QueuePage
from .pages.settings_page import SettingsPage
from .state import DeviceState, ScanState
from .workers import ScanController


class MFirmaQtWindow(MSFluentWindow):
    def __init__(
        self,
        repository: ConfigRepository | None = None,
        *,
        scan_controller: ScanController | None = None,
        auto_scan: bool = True,
    ):
        super().__init__()
        self.repository = repository or ConfigRepository()
        try:
            self.config = self.repository.load()
        except Exception:
            self.config = AppConfig()
        self.scan_controller = scan_controller or ScanController(self)
        self.queue_page = QueuePage(self)
        self.history_page = HistoryPage(self)
        self.settings_page = SettingsPage(self.config, self)
        self._build_window()
        self._connect_services()
        self._update_operational_status()
        if auto_scan and self.config.monitor.root:
            QTimer.singleShot(0, self.refresh_documents)

    def _build_window(self) -> None:
        self.setWindowTitle("mFirma — Firma PDF")
        self.resize(1180, 760)
        self.setMinimumSize(900, 620)
        self._queue_navigation = self.addSubInterface(
            self.queue_page, FluentIcon.DOCUMENT, "Da firmare"
        )
        self.addSubInterface(self.history_page, FluentIcon.HISTORY, "Cronologia")
        self.addSubInterface(self.settings_page, FluentIcon.SETTING, "Impostazioni")

    def _connect_services(self) -> None:
        self.queue_page.refreshRequested.connect(self.refresh_documents)
        self.queue_page.addFilesRequested.connect(self.add_files)
        self.queue_page.prepareRequested.connect(self._show_migration_boundary)
        self.scan_controller.scanStarted.connect(
            lambda: self.queue_page.set_scan_state(ScanState.SCANNING)
        )
        self.scan_controller.scanSucceeded.connect(self._scan_succeeded)
        self.scan_controller.scanFailed.connect(self.queue_page.set_scan_error)

    def _update_operational_status(self) -> None:
        config = self.config.pkcs11
        if config.module_path and config.certificate_label:
            state = DeviceState.READY
        elif config.module_path:
            state = DeviceState.CERTIFICATE_MISSING
        else:
            state = DeviceState.UNKNOWN
        self.queue_page.set_device_status(
            state,
            token_label=config.token_label,
            certificate_label=config.certificate_label,
        )

    @Slot()
    def refresh_documents(self) -> None:
        root = self.config.monitor.root.strip()
        if not root:
            self.queue_page.folder_status.set_status(
                "Non configurata", "Configura la cartella nella GUI stabile"
            )
            return
        self.scan_controller.start(
            Path(root),
            recursive=self.config.monitor.recursive_within_person,
            stability_seconds=self.config.monitor.stability_seconds,
            output_suffix=self.config.output.suffix,
        )

    @Slot(object)
    def _scan_succeeded(self, result: ScanResult) -> None:
        self.queue_page.set_documents(result)
        self._queue_navigation.setText(f"Da firmare ({result.total})")

    @Slot()
    def add_files(self) -> None:
        names, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            "Aggiungi uno o più PDF",
            "",
            "Documenti PDF (*.pdf)",
        )
        if not names:
            return
        try:
            documents = candidates_from_paths([Path(name) for name in names])
        except Exception:
            QMessageBox.warning(
                self,
                "Aggiungi PDF",
                "Uno o più documenti non possono essere letti.",
            )
            return
        self.queue_page.merge_documents(documents)
        self._queue_navigation.setText(
            f"Da firmare ({len(self.queue_page.model.documents)})"
        )

    @Slot(object)
    def _show_migration_boundary(self, documents) -> None:
        QMessageBox.information(
            self,
            "Controlla e firma",
            f"Hai selezionato {len(documents)} documenti.\n\n"
            "Anteprima, PIN e firma saranno collegati alla nuova interfaccia "
            "nel prossimo incremento. Per firmare ora usa l'interfaccia stabile "
            "avviando mFirma senza --qt-dashboard.",
        )

    def wait_for_workers(self, timeout_ms: int = 3000) -> bool:
        return self.scan_controller.wait_for_done(timeout_ms)
