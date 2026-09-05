from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QTableView,
    QVBoxLayout,
)
from qfluentwidgets import BodyLabel, PrimaryPushButton, PushButton, SubtitleLabel

from ...discovery import DiscoveryResult, ModuleCandidate
from ..models import ModuleTableModel


class ModuleSelectionDialog(QDialog):
    def __init__(self, result: DiscoveryResult, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Middleware PKCS#11 rilevati")
        self.setModal(True)
        self.resize(980, 420)
        self.setMinimumSize(720, 320)
        self.model = ModuleTableModel(result.candidates, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(SubtitleLabel("Scegli il middleware di firma", self))
        explanation = BodyLabel(
            "La verifica è eseguita senza PIN e fuori dal processo dell’interfaccia.",
            self,
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self.table = QTableView(self)
        self.table.setObjectName("moduleTable")
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setColumnWidth(0, 400)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 240)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = PushButton("Annulla", self)
        self.use_button = PrimaryPushButton("Usa selezionata", self)
        self.use_button.setEnabled(self.model.rowCount() > 0)
        buttons.addWidget(cancel)
        buttons.addWidget(self.use_button)
        layout.addLayout(buttons)
        cancel.clicked.connect(self.reject)
        self.use_button.clicked.connect(self.accept)
        self.table.doubleClicked.connect(lambda _index: self.accept())
        if self.model.rowCount():
            self.table.selectRow(0)

    def selected_candidate(self) -> ModuleCandidate | None:
        rows = self.table.selectionModel().selectedRows()
        return self.model.candidate(rows[0].row()) if rows else None
