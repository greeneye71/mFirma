from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QTableView,
    QVBoxLayout,
)
from qfluentwidgets import BodyLabel, PrimaryPushButton, PushButton, SubtitleLabel

from ...discovery import ModuleCandidate, TokenCandidate
from ..models import TokenTableModel


class TokenSelectionDialog(QDialog):
    def __init__(
        self,
        candidate: ModuleCandidate,
        *,
        current_label: str = "",
        current_serial: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Dispositivi di firma")
        self.setModal(True)
        self.resize(900, 400)
        self.setMinimumSize(700, 300)
        self.model = TokenTableModel(candidate.tokens, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(SubtitleLabel("Scegli il token o la smart card", self))
        explanation = BodyLabel(
            "Il seriale pubblico distingue dispositivi con la stessa etichetta. "
            "La lettura non richiede il PIN.",
            self,
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self.table = QTableView(self)
        self.table.setObjectName("tokenTable")
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for column, width in enumerate((190, 170, 180, 150, 80)):
            self.table.setColumnWidth(column, width)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = PushButton("Annulla", self)
        self.use_button = PrimaryPushButton("Usa dispositivo", self)
        self.use_button.setEnabled(self.model.rowCount() > 0)
        buttons.addWidget(cancel)
        buttons.addWidget(self.use_button)
        layout.addLayout(buttons)
        cancel.clicked.connect(self.reject)
        self.use_button.clicked.connect(self.accept)
        self.table.doubleClicked.connect(lambda _index: self.accept())

        selected_row = 0
        for row in range(self.model.rowCount()):
            token = self.model.token(row)
            if token and (
                (current_serial and token.serial_hex == current_serial)
                or (not current_serial and token.label == current_label)
            ):
                selected_row = row
                break
        if self.model.rowCount():
            self.table.selectRow(selected_row)

    def selected_token(self) -> TokenCandidate | None:
        rows = self.table.selectionModel().selectedRows()
        return self.model.token(rows[0].row()) if rows else None
