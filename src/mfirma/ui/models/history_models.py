from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from ...history import BatchHistoryRecord
from .batch_result_model import status_label, status_user_message


class HistoryBatchModel(QAbstractTableModel):
    HEADERS = ("Data e ora", "Certificato", "Documenti", "Esito")
    RECORD_ROLE = int(Qt.ItemDataRole.UserRole) + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._records: tuple[BatchHistoryRecord, ...] = ()

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._records)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(self.HEADERS)
        ):
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._records):
            return None
        record = self._records[index.row()]
        if role == self.RECORD_ROLE:
            return record
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"Batch {record.batch_id}"
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        timestamp = datetime.fromisoformat(record.created_at).astimezone()
        values = (
            timestamp.strftime("%d/%m/%Y %H:%M:%S %z"),
            record.certificate_label or "—",
            str(len(record.jobs)),
            record.outcome,
        )
        return values[index.column()]

    def set_records(self, records: tuple[BatchHistoryRecord, ...]) -> None:
        self.beginResetModel()
        self._records = tuple(records)
        self.endResetModel()

    def record_at(self, row: int) -> BatchHistoryRecord | None:
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

    @property
    def records(self) -> tuple[BatchHistoryRecord, ...]:
        return self._records


class HistoryJobModel(QAbstractTableModel):
    HEADERS = ("Documento", "Persona", "Stato", "Output", "Messaggio")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._record: BatchHistoryRecord | None = None

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        if parent.isValid() or self._record is None:
            return 0
        return len(self._record.jobs)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(self.HEADERS)
        ):
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if self._record is None or not index.isValid():
            return None
        if not 0 <= index.row() < len(self._record.jobs):
            return None
        job = self._record.jobs[index.row()]
        if role == Qt.ItemDataRole.ToolTipRole:
            return job.source
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        values = (
            Path(job.source).name,
            job.person or "—",
            status_label(job.status),
            job.output or "—",
            status_user_message(job.status, job.error_code),
        )
        return values[index.column()]

    def set_record(self, record: BatchHistoryRecord | None) -> None:
        self.beginResetModel()
        self._record = record
        self.endResetModel()
