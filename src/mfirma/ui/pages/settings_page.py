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

from ...config import AppConfig, Pkcs11Config
from ...discovery import ModuleCandidate


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
    browseOutputRequested = Signal()
    browseModuleRequested = Signal()
    discoverRequested = Signal()

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

        mode_section = _SettingsSection("Modalità di lavoro", content)
        self.mode = ComboBox(mode_section)
        self.mode.setAccessibleName("Modalità di lavoro")
        self.mode.addItem("Manuale", userData="manual")
        self.mode.addItem("Da cartella", userData="folder")
        mode_section.layout.addWidget(QLabel("Modalità"), 1, 0)
        mode_section.layout.addWidget(self.mode, 1, 1, 1, 3)
        layout.addWidget(mode_section)
        monitor = _SettingsSection("Cartella monitorata", content)
        self.monitor_section = monitor
        self.mode.currentIndexChanged.connect(self._mode_changed)
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
        self.discovery_status = BodyLabel("Nessuna lettura eseguita", device)
        self.discovery_status.setWordWrap(True)
        device.layout.addWidget(self.discovery_status, 2, 1, 1, 3)
        identity_note = BodyLabel(
            "Tessera e certificato vengono letti e scelti a ogni firma. "
            "Inserisci la tua tessera prima di premere Continua e firma.",
            device,
        )
        identity_note.setWordWrap(True)
        device.layout.addWidget(identity_note, 3, 1, 1, 3)
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
        self.output_directory = LineEdit(output)
        self.output_directory.setPlaceholderText("Vuoto: stessa cartella dell'originale")
        self.output_directory.setAccessibleName("Cartella dei file firmati")
        self.output_browse = PushButton("Sfoglia", output)
        self.output_browse.setAccessibleName("Sfoglia cartella dei file firmati")
        self.output_browse.clicked.connect(self.browseOutputRequested)
        output.layout.addWidget(QLabel("Cartella file firmati"), 2, 0)
        output.layout.addWidget(self.output_directory, 2, 1, 1, 2)
        output.layout.addWidget(self.output_browse, 2, 3)
        self.source_action = ComboBox(output)
        self.source_action.setAccessibleName("Azione sul file originale")
        for label, value in (
            ("Conserva l'originale", "keep"),
            ("Sovrascrivi l'originale con il file firmato", "overwrite"),
            ("Elimina l'originale dopo il salvataggio", "delete"),
        ):
            self.source_action.addItem(label, userData=value)
        self.source_action.currentIndexChanged.connect(self._output_action_changed)
        output.layout.addWidget(QLabel("File originale"), 3, 0)
        output.layout.addWidget(self.source_action, 3, 1, 1, 3)
        policy = BodyLabel(
            "La sovrascrittura usa nome e cartella dell'originale. L'eliminazione avviene "
            "solo dopo il salvataggio della copia firmata. Entrambe rimuovono la versione "
            "originale. Le copie firmate già esistenti vengono saltate.",
            output,
        )
        policy.setWordWrap(True)
        output.layout.addWidget(policy, 4, 1, 1, 3)
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
        self.save_button.clicked.connect(self.saveRequested)
        self.appearance_variant.currentIndexChanged.connect(self._variant_changed)
        for widget, name in (
            (self.monitor_root, "Cartella monitorata"),
            (root_browse, "Sfoglia cartella monitorata"),
            (self.recursive, "Scansiona sottocartelle della persona"),
            (self.stability_seconds, "Secondi di stabilità del file"),
            (self.module_path, "DLL PKCS11"),
            (self.discover_button, "Rileva middleware PKCS11"),
            (module_browse, "Sfoglia DLL PKCS11"),
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
            self.preset,
            self.appearance_variant,
            self.margin_points,
            self.width_points,
            self.height_points,
            self.reason,
            self.location,
            self.output_suffix,
            self.output_directory,
            self.output_browse,
            self.source_action,
            self.save_button,
        )
        for current, following in zip(tab_order, tab_order[1:]):
            QWidget.setTabOrder(current, following)

    def load_config(self, config: AppConfig) -> None:
        self._loaded_config = deepcopy(config)
        self._set_combo_data(self.mode, config.mode)
        self._mode_changed()
        self.monitor_root.setText(config.monitor.root)
        self.recursive.setChecked(config.monitor.recursive_within_person)
        self.stability_seconds.setValue(config.monitor.stability_seconds)
        self.module_path.setText(config.pkcs11.module_path)
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
        self.output_directory.setText(config.output.directory)
        self._set_combo_data(self.source_action, config.output.source_action)
        self._output_action_changed()
    def build_config(self) -> AppConfig:
        config = deepcopy(self._loaded_config)
        config.mode = str(self.mode.currentData())
        config.monitor.root = self.monitor_root.text().strip()
        config.monitor.recursive_within_person = self.recursive.isChecked()
        config.monitor.stability_seconds = self.stability_seconds.value()
        config.pkcs11 = Pkcs11Config(
            module_path=self.module_path.text().strip(),
            remembered_certificates=deepcopy(self._loaded_config.pkcs11.remembered_certificates),
        )
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
        config.output.directory = self.output_directory.text().strip()
        config.output.source_action = str(self.source_action.currentData())
        config.validate()
        return config

    def _mode_changed(self, _index: int = 0) -> None:
        self.monitor_section.setVisible(self.mode.currentData() == "folder")

    def _output_action_changed(self, _index: int = 0) -> None:
        enabled = self.source_action.currentData() != "overwrite"
        self.output_suffix.setEnabled(enabled)
        self.output_directory.setEnabled(enabled)
        self.output_browse.setEnabled(enabled)

    def mark_saved(self, config: AppConfig) -> None:
        self._loaded_config = deepcopy(config)
        self.save_status.setText("Impostazioni salvate")

    def apply_module_candidate(self, candidate: ModuleCandidate) -> None:
        self.module_path.setText(str(candidate.path))
        self.discovery_status.setText(f"Middleware verificato: {candidate.path.name}")

    def update_remembered_certificates(self, preferences: dict[str, str]) -> None:
        self._loaded_config.pkcs11.remembered_certificates = dict(preferences)

    def set_discovery_busy(self, busy: bool) -> None:
        self.discover_button.setEnabled(not busy)
        if busy:
            self.discovery_status.setText("Lettura del middleware in corso…")

    def set_discovery_error(self, message: str) -> None:
        self.discovery_status.setText(message)

    def _variant_changed(self, _index: int) -> None:
        variant = self.appearance_variant.currentData()
        width = self.width_points.value()
        height = self.height_points.value()
        if variant == "compact" and (width, height) == (212.6, 92.0):
            self.width_points.setValue(190.0)
            self.height_points.setValue(68.0)
        elif variant == "complete" and (width, height) == (190.0, 68.0):
            self.width_points.setValue(212.6)
            self.height_points.setValue(92.0)

    @staticmethod
    def _set_combo_data(combo: ComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(max(0, index))

    @property
    def selected_module_path(self) -> Path | None:
        value = self.module_path.text().strip()
        return Path(value) if value else None
