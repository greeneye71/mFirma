from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Signal, Slot
from PySide6.QtGui import (
    QCloseEvent,
    QDesktopServices,
    QGuiApplication,
    QKeySequence,
    QShowEvent,
    QShortcut,
)
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox
from qfluentwidgets import FluentIcon, MSFluentWindow

from ..batch import BatchOrchestrator
from ..config import AppConfig, ConfigRepository
from ..discovery import ModuleCandidate
from ..history import BatchHistoryRecord, HistoryRepository
from ..models import SignaturePositionPlan
from ..provider import Pkcs11SigningProvider, SigningProvider
from ..scanner import ImportResult, ScanResult
from .dialogs import (
    CertificateSelectionDialog,
    ModuleSelectionDialog,
    PinDialog,
    TokenSelectionDialog,
)
from .pages.history_page import HistoryPage
from .pages.preview_page import PreviewPage
from .pages.progress_page import ProgressPage
from .pages.queue_page import QueuePage
from .pages.result_page import ResultPage
from .pages.settings_page import SettingsPage
from .state import DeviceState, ScanState
from .tray import SystemTrayController
from .window_state import (
    WindowState,
    WindowStateRepository,
    fit_window_geometry,
)
from .workers import (
    DiscoveryController,
    DiscoveryOperation,
    DiscoveryOutcome,
    FileImportController,
    HistoryController,
    PreviewController,
    PreviewIdentity,
    PreviewResult,
    ScanController,
    SigningController,
)


LOGGER = logging.getLogger(__name__)


class MFirmaQtWindow(MSFluentWindow):
    shutdownReady = Signal()

    def __init__(
        self,
        repository: ConfigRepository | None = None,
        *,
        scan_controller: ScanController | None = None,
        import_controller: FileImportController | None = None,
        history_controller: HistoryController | None = None,
        discovery_controller: DiscoveryController | None = None,
        preview_controller: PreviewController | None = None,
        signing_controller: SigningController | None = None,
        window_state_repository: WindowStateRepository | None = None,
        tray_available: bool | None = None,
        auto_scan: bool = True,
        log_path: Path | None = None,
    ):
        super().__init__()
        self.repository = repository or ConfigRepository()
        try:
            self.config = self.repository.load()
        except Exception:
            self.config = AppConfig()
        self.window_state_repository = (
            window_state_repository
            or WindowStateRepository(
                self.repository.path.with_name("window-state.json")
            )
        )
        self.scan_controller = scan_controller or ScanController(self)
        self.import_controller = import_controller or FileImportController(self)
        self.history_controller = history_controller or HistoryController(
            HistoryRepository(self.repository.path.with_name("history.json")), self
        )
        self.discovery_controller = discovery_controller or DiscoveryController(
            self
        )
        self.preview_controller = preview_controller or PreviewController(self)
        self.signing_controller = signing_controller or SigningController(self)
        self.queue_page = QueuePage(self)
        self.preview_page = PreviewPage(self)
        self.progress_page = ProgressPage(self)
        self.log_path = log_path
        self.result_page = ResultPage(self, log_path=self.log_path)
        self.history_page = HistoryPage(self)
        self.settings_page = SettingsPage(self.config, self)
        self._shutdown_requested = False
        self._hide_notification_shown = False
        self._restore_maximized = False
        self._pending_import_paths: dict[str, Path] = {}
        self._active_certificate_label = ""
        self._shutdown_timer = QTimer(self)
        self._shutdown_timer.setInterval(100)
        self._shutdown_timer.timeout.connect(self._poll_shutdown)
        self._build_window()
        self._restore_window_state()
        self.tray_controller = SystemTrayController(
            FluentIcon.CERTIFICATE.icon(),
            self,
            available_override=tray_available,
        )
        self.setWindowIcon(FluentIcon.CERTIFICATE.icon())
        self._connect_services()
        self._update_operational_status()
        if auto_scan and self.config.monitor.root:
            QTimer.singleShot(0, self.refresh_documents)
        QTimer.singleShot(0, self._load_history)

    def _build_window(self) -> None:
        self.setWindowTitle("mFirma — Firma PDF")
        self.resize(1180, 760)
        self.setMinimumSize(900, 620)
        self._queue_navigation = self.addSubInterface(
            self.queue_page, FluentIcon.DOCUMENT, "Da firmare"
        )
        self._history_navigation = self.addSubInterface(
            self.history_page, FluentIcon.HISTORY, "Cronologia"
        )
        self._settings_navigation = self.addSubInterface(
            self.settings_page, FluentIcon.SETTING, "Impostazioni"
        )
        for button, name in (
            (self._queue_navigation, "Da firmare"),
            (self._history_navigation, "Cronologia"),
            (self._settings_navigation, "Impostazioni"),
        ):
            button.setAccessibleName(name)
            button.setToolTip(name)
        self.stackedWidget.addWidget(self.preview_page)
        self.stackedWidget.addWidget(self.progress_page)
        self.stackedWidget.addWidget(self.result_page)
        self._escape_shortcut = QShortcut(QKeySequence.Cancel, self)
        self._escape_shortcut.activated.connect(self._navigate_back)

    def _connect_services(self) -> None:
        self.queue_page.refreshRequested.connect(self.refresh_documents)
        self.queue_page.addFilesRequested.connect(self.add_files)
        self.queue_page.prepareRequested.connect(self.open_preview)
        self.preview_page.backRequested.connect(
            lambda: self.switchTo(self.queue_page)
        )
        self.preview_page.documentRequested.connect(self._prepare_preview)
        self.preview_page.continueRequested.connect(self.request_signing)
        self.progress_page.cancelRequested.connect(
            self.signing_controller.request_cancel
        )
        self.signing_controller.progressChanged.connect(
            self.progress_page.update_progress
        )
        self.signing_controller.cancellationChanged.connect(
            self.progress_page.mark_cancel_requested
        )
        self.signing_controller.batchFinished.connect(self._batch_finished)
        self.signing_controller.batchFailed.connect(self._batch_failed)
        self.signing_controller.busyChanged.connect(
            self.tray_controller.set_busy
        )
        self.tray_controller.showRequested.connect(self.restore_from_tray)
        self.tray_controller.exitRequested.connect(self.request_exit)
        self.result_page.backRequested.connect(self._return_to_documents)
        self.result_page.openFolderRequested.connect(self._open_output_folder)
        self.result_page.openLogRequested.connect(self._open_log)
        self.settings_page.saveRequested.connect(self.save_settings)
        self.settings_page.browseRootRequested.connect(self.choose_monitor_root)
        self.settings_page.browseModuleRequested.connect(self.choose_module)
        self.settings_page.discoverRequested.connect(self.discover_modules)
        self.settings_page.readCardRequested.connect(self.read_card)
        self.scan_controller.scanStarted.connect(
            lambda: self.queue_page.set_scan_state(ScanState.SCANNING)
        )
        self.scan_controller.scanSucceeded.connect(self._scan_succeeded)
        self.scan_controller.scanFailed.connect(self._scan_failed)
        self.import_controller.importSucceeded.connect(self._import_succeeded)
        self.import_controller.importFailed.connect(self._import_failed)
        self.history_controller.historyChanged.connect(self.history_page.set_records)
        self.history_controller.operationFailed.connect(self._history_failed)
        self.discovery_controller.busyChanged.connect(
            self.settings_page.set_discovery_busy
        )
        self.discovery_controller.operationSucceeded.connect(
            self._discovery_succeeded
        )
        self.discovery_controller.operationFailed.connect(self._discovery_failed)
        self.preview_controller.previewStarted.connect(
            lambda _document: self.preview_page.set_busy(True)
        )
        self.preview_controller.previewSucceeded.connect(self._preview_succeeded)
        self.preview_controller.previewFailed.connect(self._preview_failed)

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
                "Non configurata", "Configura la cartella nelle Impostazioni"
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

    @Slot(str)
    def _scan_failed(self, technical_message: str) -> None:
        LOGGER.warning("Scansione non riuscita: %s", technical_message)
        self.queue_page.set_scan_error(technical_message)

    @Slot()
    def choose_monitor_root(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Cartella contenente le persone",
            self.settings_page.monitor_root.text(),
        )
        if selected:
            self.settings_page.monitor_root.setText(selected)

    @Slot()
    def choose_module(self) -> None:
        selected, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "DLL PKCS#11",
            self.settings_page.module_path.text(),
            "Librerie Windows (*.dll);;Tutti i file (*)",
        )
        if selected:
            self.settings_page.module_path.setText(selected)
            self.discovery_controller.inspect(Path(selected))

    @Slot()
    def discover_modules(self) -> None:
        configured = self.settings_page.selected_module_path
        extra_paths = (configured,) if configured else ()
        self.discovery_controller.discover(extra_paths)

    @Slot()
    def read_card(self) -> None:
        path = self.settings_page.selected_module_path
        if path is None:
            QMessageBox.information(
                self,
                "Leggi card",
                "Prima rileva o seleziona la DLL PKCS#11 del produttore.",
            )
            return
        self.discovery_controller.inspect(path, show_certificates=True)

    @Slot(object)
    def _discovery_succeeded(self, outcome: DiscoveryOutcome) -> None:
        result = outcome.result
        if outcome.operation is DiscoveryOperation.DISCOVER:
            if not result.candidates:
                self.settings_page.set_discovery_error(
                    "Nessun middleware PKCS#11 x64 riconosciuto"
                )
                QMessageBox.information(
                    self,
                    "Rileva middleware",
                    "Nessuna DLL PKCS#11 x64 valida è stata rilevata. "
                    "Verifica che il middleware ufficiale sia installato oppure usa Sfoglia.",
                )
                return
            dialog = ModuleSelectionDialog(result, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            candidate = dialog.selected_candidate()
            if candidate is not None:
                self._apply_module_candidate(candidate)
            return

        if not result.candidates:
            name = (
                outcome.requested_path.name
                if outcome.requested_path
                else "selezionata"
            )
            self.settings_page.set_discovery_error(
                f"DLL non riconosciuta: {name}"
            )
            QMessageBox.warning(
                self,
                "Leggi certificati",
                "Il file non è un modulo PKCS#11 x64 leggibile. Controlla che sia "
                "la DLL indicata dal produttore e che abbia la stessa architettura dell’app.",
            )
            return
        self._apply_module_candidate(
            result.candidates[0],
            force_certificate_dialog=outcome.show_certificates,
        )

    def _apply_module_candidate(
        self,
        candidate: ModuleCandidate,
        *,
        force_certificate_dialog: bool = False,
    ) -> None:
        needs_confirmation = self.settings_page.apply_module_candidate(candidate)
        certificate_inventory = candidate
        if candidate.tokens:
            token = self.settings_page.selected_token(candidate)
            if len(candidate.tokens) > 1 and (
                force_certificate_dialog or token is None
            ):
                token_dialog = TokenSelectionDialog(
                    candidate,
                    current_label=self.settings_page.token_label.text().strip(),
                    current_serial=self.settings_page.token_serial.text().strip(),
                    parent=self,
                )
                if token_dialog.exec() != QDialog.DialogCode.Accepted:
                    return
                token = token_dialog.selected_token()
                if token is None:
                    return
                needs_confirmation = self.settings_page.select_token(
                    candidate, token
                )
            if token is None:
                QMessageBox.information(
                    self,
                    "Dispositivo di firma",
                    "La DLL Ã¨ valida, ma non risultano token o smart card collegati.",
                )
                return
            certificate_inventory = token

        if not (force_certificate_dialog or needs_confirmation):
            return
        if not certificate_inventory.certificate_labels:
            QMessageBox.information(
                self,
                "Certificati sulla card",
                "La card è stata letta, ma non espone certificati pubblici senza "
                "autenticazione. Alcuni middleware richiedono il proprio accesso protetto.",
            )
            return
        dialog = CertificateSelectionDialog(
            certificate_inventory,
            current_label=self.settings_page.certificate_label.text().strip(),
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            label = dialog.selected_label()
            if label:
                self.settings_page.select_certificate(certificate_inventory, label)

    @Slot(object, str)
    def _discovery_failed(
        self, operation: DiscoveryOperation, technical_message: str
    ) -> None:
        LOGGER.warning("Discovery %s non riuscita: %s", operation, technical_message)
        if operation is DiscoveryOperation.DISCOVER:
            message = (
                "Il rilevamento del middleware non è riuscito. "
                "Riprova o usa Sfoglia."
            )
        else:
            message = (
                "La lettura della DLL o della card non è riuscita. "
                "Verifica il dispositivo."
            )
        self.settings_page.set_discovery_error(message)
        QMessageBox.warning(self, "Dispositivo di firma", message)

    @Slot()
    def save_settings(self) -> None:
        try:
            config = self.settings_page.build_config()
            self.repository.save(config)
        except ValueError as exc:
            self.settings_page.save_status.setText(str(exc))
            QMessageBox.warning(self, "Impostazioni", str(exc))
            return
        except Exception:
            LOGGER.exception("Salvataggio della configurazione Qt non riuscito")
            message = "Non è stato possibile salvare le impostazioni."
            self.settings_page.save_status.setText(message)
            QMessageBox.warning(self, "Impostazioni", message)
            return
        self.config = config
        self.settings_page.mark_saved(config)
        self._update_operational_status()
        self.queue_page.folder_status.set_status(
            "Da aggiornare", "Le nuove impostazioni sono state salvate"
        )

    @Slot(object)
    def open_preview(self, documents) -> None:
        selected = tuple(documents)
        if not selected:
            return
        self.preview_page.set_documents(
            selected,
            self.config.pkcs11.certificate_label,
        )
        self.switchTo(self.preview_page)
        self._prepare_preview(0)

    @Slot(int)
    def _prepare_preview(self, index: int) -> None:
        documents = self.preview_page.documents
        if not 0 <= index < len(documents):
            return
        details = self.settings_page.selected_certificate_details
        identity = PreviewIdentity(
            certificate_label=self.config.pkcs11.certificate_label,
            subject=details.subject if details else "",
            issuer=details.issuer if details else "",
        )
        self.preview_controller.prepare(
            documents[index],
            self.config.signature,
            identity,
        )

    @Slot(object)
    def _preview_succeeded(self, result: PreviewResult) -> None:
        try:
            self.preview_page.load_preview(result)
        except ValueError as exc:
            self.preview_page.set_error(str(exc))
        except Exception:
            LOGGER.exception(
                "Visualizzazione anteprima non riuscita per %s",
                result.document.source,
            )
            self.preview_page.set_error(
                "Il documento non può essere mostrato nell’anteprima."
            )

    @Slot(object, str)
    def _preview_failed(self, document, technical_message: str) -> None:
        LOGGER.warning(
            "Preparazione anteprima non riuscita per %s: %s",
            document.source,
            technical_message,
        )
        self.preview_page.set_error(
            "Il PDF non può essere preparato per l’anteprima. Controlla il documento."
        )

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
        self.enqueue_import_paths(tuple(Path(name) for name in names))

    @Slot(object)
    def receive_external_paths(self, paths) -> None:
        self.restore_from_tray()
        if not self.signing_controller.busy:
            self.switchTo(self.queue_page)
        self.enqueue_import_paths(tuple(paths))

    def enqueue_import_paths(self, paths: tuple[Path, ...]) -> None:
        for path in paths:
            self._pending_import_paths[str(path).casefold()] = path
        self._start_pending_import()

    def _start_pending_import(self) -> None:
        if self.import_controller.busy or not self._pending_import_paths:
            return
        paths = tuple(self._pending_import_paths.values())
        self._pending_import_paths.clear()
        self.import_controller.start(paths)

    @Slot(object)
    def _import_succeeded(self, result: ImportResult) -> None:
        if result.documents:
            self.queue_page.merge_documents(result.documents, select=True)
            self._queue_navigation.setText(
                f"Da firmare ({len(self.queue_page.model.documents)})"
            )
        if result.errors:
            LOGGER.warning(
                "Importazione completata con errori: conteggio=%d dettagli=%s",
                len(result.errors),
                " | ".join(result.errors),
            )
            QMessageBox.warning(
                self,
                "Aggiungi PDF",
                f"{len(result.errors)} documenti non sono stati aggiunti. "
                "Consulta il log per i dettagli.",
            )
        self._start_pending_import()

    @Slot(str)
    def _import_failed(self, technical_message: str) -> None:
        LOGGER.error("Importazione PDF non riuscita: %s", technical_message)
        QMessageBox.warning(
            self,
            "Aggiungi PDF",
            "I documenti non possono essere aggiunti. Consulta il log errori.",
        )
        self._start_pending_import()

    @Slot()
    def _load_history(self) -> None:
        self.history_page.set_loading()
        self.history_controller.load()

    @Slot(str, str)
    def _history_failed(self, operation: str, technical_message: str) -> None:
        LOGGER.error(
            "Archivio cronologia non disponibile: operazione=%s dettaglio=%s",
            operation,
            technical_message,
        )
        self.history_page.set_error()

    @Slot(object)
    def request_signing(self, position_plan: SignaturePositionPlan) -> None:
        documents = self.preview_page.documents
        if not documents or self.signing_controller.busy:
            return
        provider = Pkcs11SigningProvider(
            self.config.pkcs11,
            self.config.signature,
        )
        try:
            provider.validate()
        except Exception as exc:
            LOGGER.warning("Configurazione di firma non pronta: %s", exc)
            QMessageBox.warning(
                self,
                "Dispositivo di firma",
                "Completa DLL e certificato nelle Impostazioni prima di firmare.",
            )
            return

        dialog = PinDialog(len(documents), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        pin = dialog.take_pin()
        try:
            self.start_batch(provider, position_plan, pin=pin)
        finally:
            pin = None

    def start_batch(
        self,
        provider: SigningProvider,
        position_plan: SignaturePositionPlan,
        *,
        pin: str | None,
    ) -> bool:
        """Avvia un batch Qt; usato anche dai test senza hardware."""

        documents = self.preview_page.documents
        if not documents:
            return False
        orchestrator = BatchOrchestrator(provider, self.config.output.suffix)
        self.progress_page.start(len(documents))
        self.switchTo(self.progress_page)
        started = self.signing_controller.start(
            orchestrator,
            documents,
            pin=pin,
            position_plan=position_plan,
        )
        if not started:
            self.switchTo(self.preview_page)
            QMessageBox.information(
                self,
                "Firma in corso",
                "Attendi il completamento del batch già avviato.",
            )
        else:
            self._active_certificate_label = self.config.pkcs11.certificate_label
        return started

    @Slot(object)
    def _batch_finished(self, jobs) -> None:
        self.result_page.set_jobs(jobs)
        self.switchTo(self.result_page)
        try:
            record = BatchHistoryRecord.from_jobs(
                jobs, certificate_label=self._active_certificate_label
            )
        except ValueError as exc:
            LOGGER.error("Esito batch non archiviabile: %s", exc)
            self.history_page.set_error()
        else:
            LOGGER.info(
                "Identificativo batch assegnato: id=%s documenti=%d",
                record.batch_id,
                len(record.jobs),
            )
            self.history_controller.append(record)
        finally:
            self._active_certificate_label = ""

    @Slot(str)
    def _batch_failed(self, technical_message: str) -> None:
        self._active_certificate_label = ""
        LOGGER.error("Worker di firma interrotto: %s", technical_message)
        self.switchTo(self.preview_page)
        QMessageBox.warning(
            self,
            "Firma non completata",
            "Il processo di firma si è interrotto. Nessun file sorgente è stato modificato.",
        )

    @Slot()
    def _return_to_documents(self) -> None:
        self.switchTo(self.queue_page)
        if self.config.monitor.root:
            self.refresh_documents()

    @Slot(object)
    def _open_output_folder(self, folder: Path) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    @Slot(object)
    def _open_log(self, path: Path) -> None:
        if not path.is_file():
            QMessageBox.information(
                self,
                "Log errori",
                "Il log non è ancora stato creato.",
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    @Slot()
    def restore_from_tray(self) -> None:
        if self._shutdown_requested:
            return
        self.show()
        self.raise_()
        self.activateWindow()

    @Slot()
    def _navigate_back(self) -> None:
        current = self.stackedWidget.currentWidget()
        if current is self.preview_page and not self.signing_controller.busy:
            self.switchTo(self.queue_page)
        elif current is self.result_page:
            self._return_to_documents()

    @Slot()
    def request_exit(self) -> None:
        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        self._save_window_state()
        self.tray_controller.set_shutting_down()
        self.hide()
        self.signing_controller.request_cancel()
        if self._workers_busy():
            self._shutdown_timer.start()
        else:
            self._finish_shutdown()

    def _workers_busy(self) -> bool:
        return any(
            controller.busy
            for controller in (
                self.scan_controller,
                self.import_controller,
                self.history_controller,
                self.discovery_controller,
                self.preview_controller,
                self.signing_controller,
            )
        )

    @Slot()
    def _poll_shutdown(self) -> None:
        if not self._workers_busy():
            self._finish_shutdown()

    def _finish_shutdown(self) -> None:
        self._shutdown_timer.stop()
        self.tray_controller.hide()
        self.shutdownReady.emit()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._save_window_state()
        if self._shutdown_requested:
            if self._workers_busy():
                event.ignore()
            else:
                event.accept()
            return
        if not self.tray_controller.available:
            if self._workers_busy():
                event.ignore()
                self.request_exit()
            else:
                event.accept()
            return
        event.ignore()
        self.hide()
        if not self._hide_notification_shown:
            self._hide_notification_shown = True
            self.tray_controller.notify_hidden()

    def _restore_window_state(self) -> None:
        try:
            state = self.window_state_repository.load()
        except Exception:
            LOGGER.warning("Stato finestra non leggibile; uso la geometria iniziale")
            return
        if state is None:
            return
        geometry = fit_window_geometry(
            state,
            (screen.availableGeometry() for screen in QGuiApplication.screens()),
            minimum_size=self.minimumSize(),
        )
        self.setGeometry(geometry)
        if state.maximized:
            self._restore_maximized = True

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if (
            self._restore_maximized
            and QGuiApplication.platformName().casefold() != "offscreen"
        ):
            self._restore_maximized = False
            QTimer.singleShot(0, self.showMaximized)

    def _save_window_state(self) -> None:
        maximized = self.isMaximized() or self._restore_maximized
        geometry = self.normalGeometry() if self.isMaximized() else self.geometry()
        state = WindowState(
            x=geometry.x(),
            y=geometry.y(),
            width=geometry.width(),
            height=geometry.height(),
            maximized=maximized,
        )
        try:
            self.window_state_repository.save(state)
        except Exception:
            LOGGER.warning("Stato finestra non salvato")

    def wait_for_workers(self, timeout_ms: int = 3000) -> bool:
        scan_done = self.scan_controller.wait_for_done(timeout_ms)
        discovery_done = self.discovery_controller.wait_for_done(timeout_ms)
        import_done = self.import_controller.wait_for_done(timeout_ms)
        history_done = self.history_controller.wait_for_done(timeout_ms)
        preview_done = self.preview_controller.wait_for_done(timeout_ms)
        signing_done = self.signing_controller.wait_for_done(timeout_ms)
        return (
            scan_done
            and import_done
            and history_done
            and discovery_done
            and preview_done
            and signing_done
        )
