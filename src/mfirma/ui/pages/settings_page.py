from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CheckBox,
    ComboBox,
    DoubleSpinBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SpinBox,
    SubtitleLabel,
    TitleLabel,
)

from ...config import AppConfig
from ...discovery import CertificateCandidate, ModuleCandidate, TokenCandidate


class _SettingsSection(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(18, 14, 18, 16)
        self.layout.setHorizontalSpacing(10)
        self.layout.setVerticalSpacing(10)
        self.layout.addWidget(SubtitleLabel(title, self), 0, 0, 1, 4)
        self.layout.setColumnStretch(1, 1)


class SettingsPage(QWidget):
    saveRequested = Signal()
    browseRootRequested = Signal()
    browseModuleRequested = Signal()
    discoverRequested = Signal()
    readCardRequested = Signal()

    PRESETS = (
        ("In alto a sinistra", "top_left"),
        ("In alto a destra", "top_right"),
        ("In basso a sinistra", "bottom_left"),
        ("In basso a destra", "bottom_right"),
    )
    VARIANTS = (("Completo", "complete"), ("Compatto", "compact"))

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self._loaded_config = deepcopy(config)
        self._certificate_ids_by_label: dict[str, str] = {}
        self._certificate_details_by_label: dict[str, CertificateCandidate] = {}
        self._certificate_id_module_path = ""
        self._certificate_id_token_serial = ""
        self._build_ui()
        self.load_config(config)

    def _build_ui(self) -> None:
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        page_layout.addWidget(scroll)
        content = QWidget(scroll)
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(TitleLabel("Impostazioni", content))
        layout.addWidget(
            BodyLabel(
                "Le modifiche diventano operative soltanto dopo il salvataggio.",
                content,
            )
        )

        monitor = _SettingsSection("Cartella monitorata", content)
        self.monitor_root = LineEdit(monitor)
        self.monitor_root.setObjectName("monitorRoot")
        self.monitor_root.setPlaceholderText("Percorso locale o UNC")
        root_browse = PushButton("Sfoglia", monitor)
        monitor.layout.addWidget(QLabel("Cartella"), 1, 0)
        monitor.layout.addWidget(self.monitor_root, 1, 1, 1, 2)
        monitor.layout.addWidget(root_browse, 1, 3)
        self.recursive = CheckBox("Scansiona le sottocartelle della persona", monitor)
        monitor.layout.addWidget(self.recursive, 2, 1, 1, 3)
        self.stability_seconds = SpinBox(monitor)
        self.stability_seconds.setRange(0, 3600)
        self.stability_seconds.setSuffix(" s")
        monitor.layout.addWidget(QLabel("Stabilità file"), 3, 0)
        monitor.layout.addWidget(self.stability_seconds, 3, 1)
        layout.addWidget(monitor)

        device = _SettingsSection("Dispositivo di firma", content)
        self.module_path = LineEdit(device)
        self.module_path.setObjectName("modulePath")
        self.module_path.setPlaceholderText("DLL PKCS#11 x64 del produttore")
        self.discover_button = PushButton("Rileva middleware", device)
        module_browse = PushButton("Sfoglia", device)
        device.layout.addWidget(QLabel("DLL PKCS#11"), 1, 0)
        device.layout.addWidget(self.module_path, 1, 1)
        device.layout.addWidget(self.discover_button, 1, 2)
        device.layout.addWidget(module_browse, 1, 3)
        self.token_label = LineEdit(device)
        self.token_label.setObjectName("tokenLabel")
        self.token_serial = LineEdit(device)
        self.token_serial.setObjectName("tokenSerial")
        self.token_serial.setReadOnly(True)
        self.token_serial.setPlaceholderText("Compilato da Leggi card")
        self.certificate_label = LineEdit(device)
        self.certificate_label.setObjectName("certificateLabel")
        self.read_card_button = PushButton("Leggi card", device)
        device.layout.addWidget(QLabel("Token"), 2, 0)
        device.layout.addWidget(self.token_label, 2, 1)
        device.layout.addWidget(QLabel("Seriale (hex)"), 2, 2)
        device.layout.addWidget(self.token_serial, 2, 3)
        device.layout.addWidget(QLabel("Certificato"), 3, 0)
        device.layout.addWidget(self.certificate_label, 3, 1, 1, 2)
        device.layout.addWidget(self.read_card_button, 3, 3)
        self.key_label = LineEdit(device)
        self.key_label.setObjectName("keyLabel")
        self.key_label.setPlaceholderText("Lasciare vuoto per associazione tramite ID")
        device.layout.addWidget(QLabel("Chiave (avanzato)"), 4, 0)
        device.layout.addWidget(self.key_label, 4, 1, 1, 3)
        self.discovery_status = BodyLabel("Nessuna lettura eseguita", device)
        self.discovery_status.setWordWrap(True)
        device.layout.addWidget(self.discovery_status, 5, 1, 1, 3)
        layout.addWidget(device)

        signature = _SettingsSection("Firma visibile", content)
        self.preset = ComboBox(signature)
        for text, value in self.PRESETS:
            self.preset.addItem(text, userData=value)
        self.appearance_variant = ComboBox(signature)
        for text, value in self.VARIANTS:
            self.appearance_variant.addItem(text, userData=value)
        signature.layout.addWidget(QLabel("Posizione"), 1, 0)
        signature.layout.addWidget(self.preset, 1, 1)
        signature.layout.addWidget(QLabel("Aspetto"), 1, 2)
        signature.layout.addWidget(self.appearance_variant, 1, 3)
        self.margin_points = DoubleSpinBox(signature)
        self.margin_points.setRange(0, 1000)
        self.margin_points.setSuffix(" pt")
        self.width_points = DoubleSpinBox(signature)
        self.width_points.setRange(1, 2000)
        self.width_points.setSuffix(" pt")
        self.height_points = DoubleSpinBox(signature)
        self.height_points.setRange(1, 2000)
        self.height_points.setSuffix(" pt")
        signature.layout.addWidget(QLabel("Margine"), 2, 0)
        signature.layout.addWidget(self.margin_points, 2, 1)
        signature.layout.addWidget(QLabel("Dimensioni"), 2, 2)
        dimensions = QHBoxLayout()
        dimensions.addWidget(self.width_points)
        dimensions.addWidget(QLabel("×"))
        dimensions.addWidget(self.height_points)
        signature.layout.addLayout(dimensions, 2, 3)
        self.reason = LineEdit(signature)
        self.location = LineEdit(signature)
        signature.layout.addWidget(QLabel("Motivo (opzionale)"), 3, 0)
        signature.layout.addWidget(self.reason, 3, 1, 1, 3)
        signature.layout.addWidget(QLabel("Luogo (opzionale)"), 4, 0)
        signature.layout.addWidget(self.location, 4, 1, 1, 3)
        layout.addWidget(signature)

        output = _SettingsSection("Output", content)
        self.output_suffix = LineEdit(output)
        self.output_suffix.setObjectName("outputSuffix")
        output.layout.addWidget(QLabel("Suffisso file firmato"), 1, 0)
        output.layout.addWidget(self.output_suffix, 1, 1)
        policy = BodyLabel(
            "Il sorgente non viene modificato. In caso di collisione il file viene saltato.",
            output,
        )
        policy.setWordWrap(True)
        output.layout.addWidget(policy, 2, 1, 1, 3)
        layout.addWidget(output)

        footer = QHBoxLayout()
        self.save_status = BodyLabel("", content)
        self.save_status.setWordWrap(True)
        self.save_button = PrimaryPushButton("Salva impostazioni", content)
        self.save_button.setObjectName("saveSettingsButton")
        footer.addWidget(self.save_status, 1)
        footer.addWidget(self.save_button)
        layout.addLayout(footer)
        layout.addStretch(1)

        root_browse.clicked.connect(self.browseRootRequested)
        module_browse.clicked.connect(self.browseModuleRequested)
        self.discover_button.clicked.connect(self.discoverRequested)
        self.read_card_button.clicked.connect(self.readCardRequested)
        self.save_button.clicked.connect(self.saveRequested)
        self.appearance_variant.currentIndexChanged.connect(self._variant_changed)
        self.module_path.textChanged.connect(self._module_edited)
        self.token_label.textEdited.connect(self._token_edited)
        for widget, name in (
            (self.monitor_root, "Cartella monitorata"),
            (root_browse, "Sfoglia cartella monitorata"),
            (self.recursive, "Scansiona sottocartelle della persona"),
            (self.stability_seconds, "Secondi di stabilità del file"),
            (self.module_path, "DLL PKCS11"),
            (self.discover_button, "Rileva middleware PKCS11"),
            (module_browse, "Sfoglia DLL PKCS11"),
            (self.token_label, "Etichetta token"),
            (self.token_serial, "Seriale pubblico token in esadecimale"),
            (self.certificate_label, "Etichetta certificato"),
            (self.read_card_button, "Leggi certificati dalla card"),
            (self.key_label, "Etichetta chiave avanzata"),
            (self.preset, "Posizione firma"),
            (self.appearance_variant, "Aspetto firma"),
            (self.margin_points, "Margine firma in punti"),
            (self.width_points, "Larghezza firma in punti"),
            (self.height_points, "Altezza firma in punti"),
            (self.reason, "Motivo firma opzionale"),
            (self.location, "Luogo firma opzionale"),
            (self.output_suffix, "Suffisso file firmato"),
            (self.save_button, "Salva impostazioni"),
        ):
            widget.setAccessibleName(name)

        tab_order = (
            self.monitor_root,
            root_browse,
            self.recursive,
            self.stability_seconds,
            self.module_path,
            self.discover_button,
            module_browse,
            self.token_label,
            self.token_serial,
            self.certificate_label,
            self.read_card_button,
            self.key_label,
            self.preset,
            self.appearance_variant,
            self.margin_points,
            self.width_points,
            self.height_points,
            self.reason,
            self.location,
            self.output_suffix,
            self.save_button,
        )
        for current, following in zip(tab_order, tab_order[1:]):
            QWidget.setTabOrder(current, following)

    def load_config(self, config: AppConfig) -> None:
        self._loaded_config = deepcopy(config)
        self.monitor_root.setText(config.monitor.root)
        self.recursive.setChecked(config.monitor.recursive_within_person)
        self.stability_seconds.setValue(config.monitor.stability_seconds)
        self.module_path.setText(config.pkcs11.module_path)
        self.token_label.setText(config.pkcs11.token_label)
        self.token_serial.setText(config.pkcs11.token_serial)
        self.certificate_label.setText(config.pkcs11.certificate_label)
        self.key_label.setText(config.pkcs11.key_label)
        self._set_combo_data(self.preset, config.signature.preset)
        self.appearance_variant.blockSignals(True)
        self._set_combo_data(
            self.appearance_variant, config.signature.appearance_variant
        )
        self.appearance_variant.blockSignals(False)
        self.margin_points.setValue(config.signature.margin_points)
        self.width_points.setValue(config.signature.width_points)
        self.height_points.setValue(config.signature.height_points)
        self.reason.setText(config.signature.reason)
        self.location.setText(config.signature.location)
        self.output_suffix.setText(config.output.suffix)
        self._certificate_ids_by_label = {}
        self._certificate_details_by_label = {}
        self._certificate_id_module_path = ""
        self._certificate_id_token_serial = ""
        if config.pkcs11.certificate_label and config.pkcs11.certificate_id:
            self._certificate_ids_by_label[config.pkcs11.certificate_label] = (
                config.pkcs11.certificate_id
            )
            self._certificate_id_module_path = config.pkcs11.module_path
            self._certificate_id_token_serial = config.pkcs11.token_serial

    def build_config(self) -> AppConfig:
        config = deepcopy(self._loaded_config)
        config.monitor.root = self.monitor_root.text().strip()
        config.monitor.recursive_within_person = self.recursive.isChecked()
        config.monitor.stability_seconds = self.stability_seconds.value()
        config.pkcs11.module_path = self.module_path.text().strip()
        config.pkcs11.token_label = self.token_label.text().strip()
        config.pkcs11.token_serial = self.token_serial.text().strip()
        config.pkcs11.certificate_label = self.certificate_label.text().strip()
        config.pkcs11.key_label = self.key_label.text().strip()
        if (
            config.pkcs11.module_path == self._certificate_id_module_path
            and config.pkcs11.token_serial == self._certificate_id_token_serial
        ):
            config.pkcs11.certificate_id = self._certificate_ids_by_label.get(
                config.pkcs11.certificate_label, ""
            )
        else:
            config.pkcs11.certificate_id = ""
        config.signature.preset = str(self.preset.currentData())
        config.signature.appearance_variant = str(
            self.appearance_variant.currentData()
        )
        config.signature.margin_points = self.margin_points.value()
        config.signature.width_points = self.width_points.value()
        config.signature.height_points = self.height_points.value()
        config.signature.reason = self.reason.text().strip()
        config.signature.location = self.location.text().strip()
        config.output.suffix = self.output_suffix.text().strip()
        config.validate()
        return config

    def mark_saved(self, config: AppConfig) -> None:
        self._loaded_config = deepcopy(config)
        self.save_status.setText("Impostazioni salvate")

    def apply_module_candidate(self, candidate: ModuleCandidate) -> bool:
        self.module_path.setText(str(candidate.path))
        if candidate.tokens:
            selected = candidate.find_token(
                self.token_label.text().strip(), self.token_serial.text().strip()
            )
            if selected is None and len(candidate.tokens) == 1:
                selected = candidate.tokens[0]
            if selected is not None:
                return self.select_token(candidate, selected)
            self._clear_certificate_inventory()
            self.discovery_status.setText(
                f"{len(candidate.tokens)} dispositivi rilevati: scegline uno"
            )
            return False

        # CompatibilitÃ  con risultati prodotti da versioni precedenti.
        self._certificate_ids_by_label = dict(candidate.certificate_ids)
        self._certificate_details_by_label = {
            certificate.label: certificate for certificate in candidate.certificates
        }
        self._certificate_id_module_path = str(candidate.path)
        self._certificate_id_token_serial = ""
        current_token = self.token_label.text().strip()
        if (
            len(candidate.token_labels) == 1
            and current_token not in candidate.token_labels
        ):
            self.token_label.setText(candidate.token_labels[0])
        current_certificate = self.certificate_label.text().strip()
        needs_confirmation = False
        if current_certificate not in candidate.certificate_labels:
            if len(candidate.document_signing_labels) == 1:
                self.certificate_label.setText(candidate.document_signing_labels[0])
            elif len(candidate.certificate_labels) == 1:
                self.certificate_label.setText(candidate.certificate_labels[0])
            elif len(candidate.certificate_labels) > 1:
                needs_confirmation = True
        count = len(candidate.certificate_labels)
        self.discovery_status.setText(
            f"{count} certificati pubblici letti da {candidate.path.name}"
            if count
            else f"DLL verificata: {candidate.path.name}; nessun certificato pubblico"
        )
        return needs_confirmation

    def select_token(
        self, candidate: ModuleCandidate, token: TokenCandidate
    ) -> bool:
        if token not in candidate.tokens:
            raise ValueError("Dispositivo non presente nella lettura corrente")
        self.token_label.setText(token.label)
        self.token_serial.setText(token.serial_hex)
        needs_confirmation = self._apply_certificate_inventory(
            token, str(candidate.path), token.serial_hex
        )
        count = len(token.certificate_labels)
        description = token.label or token.serial or str(token.slot_id)
        self.discovery_status.setText(
            f"{count} certificati pubblici letti da {description}"
            if count
            else f"Dispositivo letto: {description}; nessun certificato pubblico"
        )
        return needs_confirmation

    def selected_token(self, candidate: ModuleCandidate) -> TokenCandidate | None:
        return candidate.find_token(
            self.token_label.text().strip(), self.token_serial.text().strip()
        )

    def _apply_certificate_inventory(
        self,
        inventory: ModuleCandidate | TokenCandidate,
        module_path: str,
        token_serial: str,
    ) -> bool:
        self._certificate_ids_by_label = dict(inventory.certificate_ids)
        self._certificate_details_by_label = {
            certificate.label: certificate for certificate in inventory.certificates
        }
        self._certificate_id_module_path = module_path
        self._certificate_id_token_serial = token_serial
        current_certificate = self.certificate_label.text().strip()
        if current_certificate in inventory.certificate_labels:
            return False
        if len(inventory.document_signing_labels) == 1:
            self.certificate_label.setText(inventory.document_signing_labels[0])
            return False
        if len(inventory.certificate_labels) == 1:
            self.certificate_label.setText(inventory.certificate_labels[0])
            return False
        self.certificate_label.clear()
        return len(inventory.certificate_labels) > 1

    def select_certificate(
        self, candidate: ModuleCandidate | TokenCandidate, label: str
    ) -> None:
        if label not in candidate.certificate_labels:
            raise ValueError("Certificato non presente nella card letta")
        self.certificate_label.setText(label)
        self.discovery_status.setText(f"Certificato selezionato: {label}")

    def _clear_certificate_inventory(self) -> None:
        self._certificate_ids_by_label = {}
        self._certificate_details_by_label = {}
        self._certificate_id_module_path = ""
        self._certificate_id_token_serial = ""
        self.certificate_label.clear()

    def _module_edited(self, _text: str) -> None:
        self.token_serial.clear()
        self._clear_certificate_inventory()

    def _token_edited(self, _text: str) -> None:
        self.token_serial.clear()
        self._clear_certificate_inventory()

    def set_discovery_busy(self, busy: bool) -> None:
        self.discover_button.setEnabled(not busy)
        self.read_card_button.setEnabled(not busy)
        if busy:
            self.discovery_status.setText("Lettura del middleware in corso…")

    def set_discovery_error(self, message: str) -> None:
        self.discovery_status.setText(message)

    def _variant_changed(self, _index: int) -> None:
        variant = self.appearance_variant.currentData()
        width = self.width_points.value()
        height = self.height_points.value()
        if variant == "compact" and (width, height) == (240.0, 92.0):
            self.width_points.setValue(190.0)
            self.height_points.setValue(68.0)
        elif variant == "complete" and (width, height) == (190.0, 68.0):
            self.width_points.setValue(240.0)
            self.height_points.setValue(92.0)

    @staticmethod
    def _set_combo_data(combo: ComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(max(0, index))

    @property
    def selected_module_path(self) -> Path | None:
        value = self.module_path.text().strip()
        return Path(value) if value else None

    @property
    def selected_certificate_details(self) -> CertificateCandidate | None:
        return self._certificate_details_by_label.get(
            self.certificate_label.text().strip()
        )
