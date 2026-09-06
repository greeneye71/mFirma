from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QTableView,
    QVBoxLayout,
)
from qfluentwidgets import BodyLabel, CheckBox, PrimaryPushButton, PushButton, SubtitleLabel

from ...discovery import CertificateCandidate, ModuleCandidate, TokenCandidate
from ..models import CertificateTableModel


class CertificateSelectionDialog(QDialog):
    def __init__(
        self,
        candidate: ModuleCandidate | TokenCandidate,
        *,
        current_label: str = "",
        current_id: str = "",
        allow_remember: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Certificati sulla card")
        self.setModal(True)
        self.resize(1080, 430)
        self.setMinimumSize(760, 320)
        self.model = CertificateTableModel(candidate, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(SubtitleLabel("Scegli il certificato di firma", self))
        explanation = BodyLabel(
            "Sono mostrati soltanto certificati pubblici letti senza PIN. "
            + ("Più certificati consentono la firma documenti: scegli quello da usare."
               if any(item.content_commitment for item in candidate.certificates)
               else "Nessun certificato dichiara l'uso Firma documenti: verifica quale utilizzare."),
            self,
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self.table = QTableView(self)
        self.table.setObjectName("certificateTable")
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for column, width in enumerate((190, 170, 280, 280, 110)):
            self.table.setColumnWidth(column, width)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)
        self.remember_choice = CheckBox("Ricorda la scelta per questa tessera", self)
        self.remember_choice.setVisible(allow_remember)
        self.remember_choice.setChecked(allow_remember and bool(current_id))
        self.remember_choice.setToolTip("La scelta viene riproposta soltanto per questa tessera e resta da confermare.")
        layout.addWidget(self.remember_choice)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = PushButton("Annulla", self)
        self.use_button = PrimaryPushButton("Usa certificato", self)
        self.use_button.setEnabled(self.model.rowCount() > 0)
        buttons.addWidget(cancel)
        buttons.addWidget(self.use_button)
        layout.addLayout(buttons)
        cancel.clicked.connect(self.reject)
        self.use_button.clicked.connect(self.accept)
        self.table.doubleClicked.connect(lambda _index: self.accept())

        selected_row = 0
        for row in range(self.model.rowCount()):
            certificate = self.model.certificate(row)
            if certificate and (
                certificate.id_hex == current_id if current_id
                else certificate.label == current_label
            ):
                selected_row = row
                break
        if self.model.rowCount():
            self.table.selectRow(selected_row)
        self.table.selectionModel().selectionChanged.connect(self._selection_changed)
        self._selection_changed()

    def _selection_changed(self, *_args) -> None:
        certificate = self.selected_certificate()
        self.remember_choice.setEnabled(bool(certificate and certificate.id_hex))
        if not self.remember_choice.isEnabled():
            self.remember_choice.setChecked(False)

    def selected_label(self) -> str:
        certificate = self.selected_certificate()
        return certificate.label if certificate else ""

    def selected_certificate(self) -> CertificateCandidate | None:
        rows = self.table.selectionModel().selectedRows()
        return self.model.certificate(rows[0].row()) if rows else None
