from __future__ import annotations

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, CaptionLabel, PushButton, SubtitleLabel, TitleLabel

from ...history import BatchHistoryRecord
from ..models import HistoryBatchModel, HistoryJobModel


class HistoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("historyPage")
        self.model = HistoryBatchModel(self)
        self.job_model = HistoryJobModel(self)
        self._selected_record: BatchHistoryRecord | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(TitleLabel("Cronologia", self))

        self.status_label = BodyLabel("Caricamento della cronologia…", self)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.table = QTableView(self)
        self.table.setObjectName("historyBatchTable")
        self.table.setAccessibleName("Batch di firma archiviati")
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(False)
        for column, width in enumerate((190, 280, 100, 170)):
            self.table.setColumnWidth(column, width)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.selectionModel().currentRowChanged.connect(self._select_record)
        layout.addWidget(self.table, 1)

        self.detail_title = SubtitleLabel("Dettaglio batch", self)
        layout.addWidget(self.detail_title)
        identity_layout = QHBoxLayout()
        self.batch_id_label = CaptionLabel("", self)
        self.batch_id_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.copy_id_button = PushButton("Copia ID batch", self)
        self.copy_id_button.setAccessibleName(
            "Copia l'identificativo del batch selezionato"
        )
        identity_layout.addWidget(self.batch_id_label, 1)
        identity_layout.addWidget(self.copy_id_button)
        layout.addLayout(identity_layout)

        self.job_table = QTableView(self)
        self.job_table.setObjectName("historyJobTable")
        self.job_table.setAccessibleName("Esiti del batch selezionato")
        self.job_table.setModel(self.job_model)
        self.job_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.job_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for column, width in enumerate((220, 130, 100, 300, 280)):
            self.job_table.setColumnWidth(column, width)
        self.job_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.job_table, 1)

        self.copy_id_button.clicked.connect(self.copy_batch_id)
        self.set_records(())

    def set_loading(self) -> None:
        self.status_label.setText("Caricamento della cronologia…")
        self.status_label.show()

    def set_records(self, records: tuple[BatchHistoryRecord, ...]) -> None:
        self.model.set_records(records)
        has_records = bool(records)
        self.table.setVisible(has_records)
        self.detail_title.setVisible(has_records)
        self.batch_id_label.setVisible(has_records)
        self.copy_id_button.setVisible(has_records)
        self.job_table.setVisible(has_records)
        if has_records:
            self.status_label.hide()
            self.table.selectRow(0)
            self._show_record(records[0])
        else:
            self.status_label.setText("Non sono ancora stati eseguiti batch di firma.")
            self.status_label.show()
            self._show_record(None)

    def set_error(self) -> None:
        self.status_label.setText(
            "La cronologia non può essere aggiornata. Consulta il log errori."
        )
        self.status_label.show()

    def _select_record(self, current: QModelIndex, _previous: QModelIndex) -> None:
        self._show_record(self.model.record_at(current.row()))

    def _show_record(self, record: BatchHistoryRecord | None) -> None:
        self._selected_record = record
        self.job_model.set_record(record)
        self.batch_id_label.setText(
            f"ID batch: {record.batch_id}" if record is not None else ""
        )
        self.copy_id_button.setEnabled(record is not None)

    def copy_batch_id(self) -> None:
        if self._selected_record is not None:
            QApplication.clipboard().setText(self._selected_record.batch_id)
