from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QVBoxLayout
from qfluentwidgets import (
    BodyLabel,
    CheckBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
)


class PinDialog(QDialog):
    def __init__(self, document_count: int, parent=None, *, certificate: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Inserisci il PIN del dispositivo")
        self.setModal(True)
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        layout.addWidget(SubtitleLabel("Inserisci il PIN del dispositivo", self))
        explanation = BodyLabel(
            "Il PIN serve solo per questa operazione e non verrà salvato.", self
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.certificate_label = BodyLabel(certificate, self)
        self.certificate_label.setWordWrap(True)
        self.certificate_label.setVisible(bool(certificate))
        layout.addWidget(self.certificate_label)
        self.pin_edit = LineEdit(self)
        self.pin_edit.setObjectName("pinEntry")
        self.pin_edit.setAccessibleName("PIN del dispositivo")
        self.pin_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin_edit.setInputMethodHints(
            Qt.InputMethodHint.ImhHiddenText
            | Qt.InputMethodHint.ImhNoPredictiveText
            | Qt.InputMethodHint.ImhNoAutoUppercase
        )
        self.pin_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        layout.addWidget(self.pin_edit)
        self.protected_prompt = CheckBox(
            "Il middleware richiede il PIN nel proprio dialogo protetto", self
        )
        self.protected_prompt.toggled.connect(
            lambda checked: self.pin_edit.setEnabled(not checked)
        )
        layout.addWidget(self.protected_prompt)
        note = BodyLabel(
            "Il middleware può chiedere nuovamente il PIN. Dopo un errore non "
            "verranno effettuati tentativi automatici.",
            self,
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = PushButton("Annulla", self)
        confirm = PrimaryPushButton(f"Firma {document_count} documenti", self)
        buttons.addWidget(cancel)
        buttons.addWidget(confirm)
        layout.addLayout(buttons)
        cancel.clicked.connect(self.reject)
        confirm.clicked.connect(self.accept)

    def take_pin(self) -> str | None:
        value = None if self.protected_prompt.isChecked() else self.pin_edit.text()
        self.pin_edit.clear()
        return value or None

    def reject(self) -> None:
        self.pin_edit.clear()
        super().reject()
