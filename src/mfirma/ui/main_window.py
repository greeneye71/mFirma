from __future__ import annotations

import logging
from copy import deepcopy
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
from qfluentwidgets import FluentIcon, MSFluentWindow, NavigationItemPosition

from ..batch import BatchOrchestrator
from ..config import AppConfig, ConfigRepository, Pkcs11Config
from ..discovery import ModuleCandidate
from ..history import BatchHistoryRecord, HistoryRepository
from ..identity import signer_display_name
from ..signature_register import IncompleteRegisterError, JsonlSignatureRegister, SigningIdentity
from ..models import DocumentCandidate, SignaturePositionPlan
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
        signing_discovery_controller: DiscoveryController | None = None,
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
        self.signing_discovery_controller = signing_discovery_controller or DiscoveryController(self)
        self._pending_signing: tuple[
            SignaturePositionPlan, tuple[DocumentCandidate, ...], AppConfig
        ] | None = None
        self.preview_controller = preview_controller or PreviewController(self)
        self.signing_controller = signing_controller or SigningController(self)
        self.queue_page = QueuePage(self)
        self.preview_page = PreviewPage(self)
        self.progress_page = ProgressPage(self)
        self.log_path = log_path
        self.signature_register = JsonlSignatureRegister(self.repository.path.with_name("signatures.jsonl"))
        self.result_page = ResultPage(self, log_path=self.log_path)
        self.history_page = HistoryPage(self)
        self.history_page.set_register_path(self.signature_register.path)
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
        if auto_scan and self.config.mode == "folder" and self.config.monitor.root:
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
            self.settings_page, FluentIcon.SETTING, "Impostazioni",
            position=NavigationItemPosition.BOTTOM,
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
        self.settings_page.browseOutputRequested.connect(self.choose_output_directory)
        self.settings_page.browseModuleRequested.connect(self.choose_module)
        self.settings_page.discoverRequested.connect(self.discover_modules)
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
        self.signing_discovery_controller.operationSucceeded.connect(self._signing_card_read)
        self.signing_discovery_controller.operationFailed.connect(self._signing_card_failed)
        self.preview_controller.previewStarted.connect(
            lambda _document: self.preview_page.set_busy(True)
        )
        self.preview_controller.previewSucceeded.connect(self._preview_succeeded)
        self.preview_controller.previewFailed.connect(self._preview_failed)

    def _update_operational_status(self) -> None:
        self.queue_page.configure_mode(self.config.mode, self.config.monitor.root)

    @Slot()
    def refresh_documents(self) -> None:
        if self.config.mode != "folder":
            return
        root = self.config.monitor.root.strip()
        if not root:
            self.queue_page.show_warning("Configura la cartella nelle Impostazioni")
            return
        self.scan_controller.start(
            Path(root),
            recursive=self.config.monitor.recursive_within_person,
            stability_seconds=self.config.monitor.stability_seconds,
            output_suffix=self.config.output.suffix,
        )

    @Slot(object)
    def _scan_succeeded(self, result: ScanResult) -> None:
        if self.config.mode != "folder":
            return
        self.queue_page.set_documents(result)
        self._queue_navigation.setText(f"Da firmare ({result.total})")

    @Slot(str)
    def _scan_failed(self, technical_message: str) -> None:
        LOGGER.warning("Scansione non riuscita: %s", technical_message)
        if self.config.mode == "folder":
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
    def choose_output_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Cartella dei file firmati", self.settings_page.output_directory.text(),
        )
        if selected:
            self.settings_page.output_directory.setText(selected)

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
        self._apply_module_candidate(result.candidates[0])

    def _apply_module_candidate(
        self,
        candidate: ModuleCandidate,
    ) -> None:
        self.settings_page.apply_module_candidate(candidate)

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
        if self.config.mode == "folder":
            self.queue_page.updated_label.setText("Impostazioni salvate · premi Aggiorna")

    @Slot(object)
    def open_preview(self, documents) -> None:
        selected = tuple(documents)
        if not selected:
            return
        self.preview_page.set_documents(
            selected,
            "Da scegliere dalla tessera al momento della firma",
        )
        output = self.config.output
        output_text = {
            "keep": "Originali conservati",
            "overwrite": "Gli originali saranno sostituiti dai PDF firmati",
            "delete": "Gli originali saranno eliminati dopo il salvataggio",
        }[output.source_action]
        if output.source_action != "overwrite":
            output_text += "\nDestinazione: " + (output.directory or "cartella dell'originale")
        self.preview_page.output_label.setText(output_text)
        self.switchTo(self.preview_page)
        self._prepare_preview(0)

    @Slot(int)
    def _prepare_preview(self, index: int) -> None:
        documents = self.preview_page.documents
        if not 0 <= index < len(documents):
            return
        identity = PreviewIdentity()
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
        if not documents or self.signing_controller.busy or self._pending_signing is not None:
            return
        if not self._prepare_signature_register():
            return
        if not self.config.pkcs11.module_path:
            QMessageBox.warning(
                self, "Dispositivo di firma",
                "Seleziona e salva la DLL PKCS#11 nelle Impostazioni prima di firmare.",
            )
            return
        self._pending_signing = (position_plan, tuple(documents), deepcopy(self.config))
        self.preview_page.setEnabled(False)
        self.preview_page.certificate_label.setText("Lettura della tessera in corso…")
        if not self.signing_discovery_controller.inspect(Path(self.config.pkcs11.module_path)):
            self._finish_signing_request()

    def _prepare_signature_register(self) -> bool:
        try:
            self.signature_register.prepare()
        except IncompleteRegisterError:
            answer = QMessageBox.question(
                self, "Recupero registro firme",
                "Il registro contiene una riga finale incompleta. Creare una copia integrale "
                "di sicurezza e recuperare le righe leggibili? La parte incompleta resterà "
                "nel backup. Eventuali firme non registrate richiedono un controllo manuale.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
            try:
                backup = self.signature_register.recover_incomplete_tail()
                self.signature_register.prepare()
            except Exception:
                QMessageBox.warning(self, "Registro firme", "Recupero non riuscito. Nessuna firma avviata; verificare il registro e le copie di sicurezza.")
                return False
            QMessageBox.information(self, "Registro recuperato",
                                    f"Copia di sicurezza: {backup}\nControllare gli esiti dell'operazione interrotta prima di riprovare la firma.")
            # Nuova azione esplicita dopo il controllo degli esiti, mai rifirma automatica.
            return False
        except Exception:
            QMessageBox.warning(self, "Registro firme", "Registro non disponibile. Nessuna firma avviata.")
            return False
        return True

    def _finish_signing_request(self) -> None:
        self._pending_signing = None
        self.preview_page.setEnabled(True)
        self.preview_page.certificate_label.setText(
            "Da scegliere dalla tessera al momento della firma"
        )

    @Slot(object, str)
    def _signing_card_failed(self, operation, technical_message: str) -> None:
        LOGGER.warning("Lettura tessera per la firma non riuscita: %s", technical_message)
        self._finish_signing_request()
        if not self._shutdown_requested:
            QMessageBox.warning(
                self, "Tessera di firma",
                "Impossibile leggere la tessera. Verifica il collegamento e riprova.",
            )

    @Slot(object)
    def _signing_card_read(self, outcome: DiscoveryOutcome) -> None:
        pending = self._pending_signing
        if pending is None:
            return
        try:
            position_plan, documents, config = pending
            if (self._shutdown_requested
                    or self.stackedWidget.currentWidget() is not self.preview_page
                    or tuple(self.preview_page.documents) != documents):
                return
            candidates = outcome.result.candidates
            module_path = Path(config.pkcs11.module_path).resolve()
            candidate = next(
                (item for item in candidates if item.path.resolve() == module_path), None
            )
            if candidate is None or not candidate.tokens:
                QMessageBox.information(
                    self, "Tessera di firma",
                    "Nessuna tessera leggibile. Inserisci la tua tessera e riprova.",
                )
                return
            if len(candidate.tokens) == 1:
                token = candidate.tokens[0]
            else:
                token_dialog = TokenSelectionDialog(candidate, parent=self)
                if token_dialog.exec() != QDialog.DialogCode.Accepted:
                    return
                token = token_dialog.selected_token()
                if token is None:
                    return
            if not token.serial_hex:
                QMessageBox.warning(
                    self, "Tessera di firma",
                    "Il middleware non fornisce il seriale della tessera: "
                    "non è possibile identificarla in modo sicuro per questa firma.",
                )
                return
            if not token.certificates:
                QMessageBox.information(
                    self, "Certificati sulla tessera",
                    "La tessera non espone certificati pubblici leggibili. "
                    "Verifica il middleware del produttore e riprova.",
                )
                return
            preference_key = str(module_path).casefold() + "|" + token.serial_hex.casefold()
            remembered_id = config.pkcs11.remembered_certificates.get(preference_key, "")
            if not any(item.id_hex == remembered_id for item in token.certificates):
                remembered_id = ""
            signing_certificates = [item for item in token.certificates if item.content_commitment]
            remember_choice = None
            if len(signing_certificates) == 1:
                certificate = signing_certificates[0]
            else:
                certificate_dialog = CertificateSelectionDialog(
                    token, current_id=remembered_id, allow_remember=True, parent=self,
                )
                if certificate_dialog.exec() != QDialog.DialogCode.Accepted:
                    return
                certificate = certificate_dialog.selected_certificate()
                remember_choice = certificate_dialog.remember_choice.isChecked()
            if certificate is None:
                return
            if certificate.id_hex and sum(
                item.id_hex == certificate.id_hex for item in token.certificates
            ) != 1:
                QMessageBox.warning(
                    self, "Certificato di firma",
                    "Il middleware espone più certificati con lo stesso ID. "
                    "Non è possibile identificare univocamente quello scelto.",
                )
                return
            if not certificate.id_hex and sum(
                item.label == certificate.label for item in token.certificates
            ) != 1:
                QMessageBox.warning(
                    self, "Certificato di firma",
                    "Il certificato non ha un ID e la sua etichetta non è univoca.",
                )
                return
            # Identità esclusiva di questo batch: nessun dato della persona precedente.
            runtime_pkcs11 = Pkcs11Config(
                module_path=str(module_path),
                token_label=token.label,
                token_serial=token.serial_hex,
                certificate_label=certificate.label,
                certificate_id=certificate.id_hex,
            )
            provider = Pkcs11SigningProvider(runtime_pkcs11, config.signature)
            provider.expected_certificate_sha256 = certificate.sha256
            signing_identity = SigningIdentity(
                signer_name=signer_display_name(certificate.subject, certificate.label),
                token_label=token.label, token_serial=token.serial_hex,
                certificate_label=certificate.label, certificate_id=certificate.id_hex,
                certificate_serial=certificate.serial_number,
                certificate_subject=certificate.subject, certificate_issuer=certificate.issuer,
                certificate_sha256=certificate.sha256,
            )
            try:
                provider.validate()
            except Exception as exc:
                LOGGER.warning("Dispositivo di firma non pronto: %s", exc)
                QMessageBox.warning(
                    self, "Dispositivo di firma",
                    "Il dispositivo selezionato non è pronto. Verifica il middleware e riprova.",
                )
                return
            identity_text = "\n".join(filter(None, (
                signer_display_name(certificate.subject, certificate.label),
                f"Tessera: {token.label} · {token.serial or token.serial_hex}",
            )))
            pin_dialog = PinDialog(len(documents), self, certificate=identity_text)
            if pin_dialog.exec() != QDialog.DialogCode.Accepted:
                return
            pin = pin_dialog.take_pin()
            try:
                if self._shutdown_requested:
                    return
                if remember_choice is not None:
                    self._remember_certificate(
                        preference_key, certificate.id_hex if remember_choice else "",
                    )
                if self._shutdown_requested:
                    return
                self.start_batch(
                    provider, position_plan, pin=pin, documents=documents,
                    batch_config=config,
                    signing_identity=signing_identity,
                    certificate_label=" · ".join(filter(None, (certificate.label, certificate.subject))),
                )
            finally:
                pin = None
        finally:
            self._finish_signing_request()

    def _remember_certificate(self, key: str, certificate_id: str) -> None:
        config = deepcopy(self.config)
        if certificate_id:
            config.pkcs11.remembered_certificates[key] = certificate_id
        else:
            config.pkcs11.remembered_certificates.pop(key, None)
        # Rimuove l'identità globale eventualmente lasciata dalle vecchie versioni.
        config.pkcs11 = Pkcs11Config(
            module_path=config.pkcs11.module_path,
            remembered_certificates=config.pkcs11.remembered_certificates,
        )
        try:
            self.repository.save(config)
        except Exception:
            LOGGER.warning("Preferenza del certificato non salvata")
            QMessageBox.warning(
                self, "Preferenza certificato",
                "Non è stato possibile ricordare la scelta. La firma può proseguire.",
            )
            return
        self.config = config
        self.settings_page.update_remembered_certificates(config.pkcs11.remembered_certificates)

    def start_batch(
        self,
        provider: SigningProvider,
        position_plan: SignaturePositionPlan,
        *,
        pin: str | None,
        documents: tuple[DocumentCandidate, ...] | None = None,
        batch_config: AppConfig | None = None,
        certificate_label: str = "",
        signing_identity: SigningIdentity | None = None,
    ) -> bool:
        """Avvia un batch Qt; usato anche dai test senza hardware."""

        documents = self.preview_page.documents if documents is None else documents
        if not documents:
            return False
        config = batch_config or self.config
        orchestrator = BatchOrchestrator(
            provider, config.output.suffix,
            output_directory=Path(config.output.directory) if config.output.directory else None,
            source_action=config.output.source_action,
            register=self.signature_register,
            signing_identity=signing_identity,
            mode=config.mode,
        )
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
            self._active_certificate_label = certificate_label
        return started

    @Slot(object)
    def _batch_finished(self, jobs) -> None:
        self.result_page.set_jobs(jobs)
        self.switchTo(self.result_page)
        try:
            record = BatchHistoryRecord.from_jobs(
                jobs, certificate_label=self._active_certificate_label,
                batch_id=jobs[0].batch_id or None,
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
            "Il processo di firma si è interrotto. I documenti già completati mantengono le modifiche applicate.",
        )

    @Slot()
    def _return_to_documents(self) -> None:
        self.switchTo(self.queue_page)
        if self.config.mode == "folder" and self.config.monitor.root:
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
                self.signing_discovery_controller,
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
        signing_discovery_done = self.signing_discovery_controller.wait_for_done(timeout_ms)
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
            and signing_discovery_done
            and preview_done
            and signing_done
        )
