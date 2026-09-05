from PySide6.QtWidgets import QFormLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, TitleLabel

from ...config import AppConfig


class SettingsPage(QWidget):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(TitleLabel("Impostazioni", self))
        note = BodyLabel(
            "Questa pagina diventerà modificabile nel prossimo incremento Qt. "
            "Durante la migrazione la configurazione stabile resta nella GUI attuale.",
            self,
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        form.addRow("Cartella", BodyLabel(config.monitor.root or "Non configurata", self))
        form.addRow("DLL PKCS#11", BodyLabel(config.pkcs11.module_path or "Non configurata", self))
        form.addRow("Certificato", BodyLabel(config.pkcs11.certificate_label or "Non configurato", self))
        form.addRow("Aspetto", BodyLabel(config.signature.appearance_variant, self))
        form.addRow("Output", BodyLabel(f"Stessa cartella · {config.output.suffix}", self))
        layout.addLayout(form)
        layout.addStretch(1)
