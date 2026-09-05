from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QTableView,
    QVBoxLayout,
)
from qfluentwidgets import BodyLabel, PrimaryPushButton, PushButton, SubtitleLabel

from ...discovery import ModuleCandidate
from ..models import CertificateTableModel


class CertificateSelectionDialog(QDialog):
    def __init__(
        self,
        candidate: ModuleCandidate,
        *,
        current_label: str = "",
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
            "“Firma documenti” indica l’uso contentCommitment dichiarato dal certificato.",
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
            if certificate and certificate.label == current_label:
                selected_row = row
                break
        if self.model.rowCount():
            self.table.selectRow(selected_row)

    def selected_label(self) -> str:
        rows = self.table.selectionModel().selectedRows()
        certificate = self.model.certificate(rows[0].row()) if rows else None
        return certificate.label if certificate else ""
