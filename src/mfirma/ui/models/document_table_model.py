from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal

from ...models import DocumentCandidate
from ..state import normalized_path


class DocumentTableModel(QAbstractTableModel):
    selectionChanged = Signal(int)

    CHECK_COLUMN = 0
    DOCUMENT_COLUMN = 1
    PERSON_COLUMN = 2
    WAITING_COLUMN = 3
    SIZE_COLUMN = 4
    HEADERS = ("", "Documento", "Persona", "In attesa da", "Dimensione")
    DOCUMENT_ROLE = int(Qt.ItemDataRole.UserRole) + 1
    SORT_ROLE = int(Qt.ItemDataRole.UserRole) + 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self._documents: list[DocumentCandidate] = []
        self._selected_paths: set[str] = set()

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._documents)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
            and 0 <= section < len(self.HEADERS)
        ):
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._documents):
            return None
        document = self._documents[index.row()]
        column = index.column()
        if role == self.DOCUMENT_ROLE:
            return document
        if role == Qt.ItemDataRole.ToolTipRole:
            return str(document.source)
        if role == Qt.ItemDataRole.CheckStateRole and column == self.CHECK_COLUMN:
            return (
                Qt.CheckState.Checked
                if normalized_path(document.source) in self._selected_paths
                else Qt.CheckState.Unchecked
            )
        if role == Qt.ItemDataRole.TextAlignmentRole and column == self.SIZE_COLUMN:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == self.SORT_ROLE:
            return self._sort_value(document, column)
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if column == self.CHECK_COLUMN:
            return ""
        if column == self.DOCUMENT_COLUMN:
            return document.source.name
        if column == self.PERSON_COLUMN:
            return document.person or "—"
        if column == self.WAITING_COLUMN:
            return self._waiting_text(document.modified_ns)
        if column == self.SIZE_COLUMN:
            return self._format_size(document.size)
        return None

    def flags(self, index: QModelIndex):
        flags = super().flags(index)
        if index.isValid() and index.column() == self.CHECK_COLUMN:
            flags |= Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
        return flags

    def setData(  # noqa: N802
        self, index: QModelIndex, value, role=Qt.ItemDataRole.EditRole
    ) -> bool:
        if (
            not index.isValid()
            or index.column() != self.CHECK_COLUMN
            or role != Qt.ItemDataRole.CheckStateRole
        ):
            return False
        key = normalized_path(self._documents[index.row()].source)
        if value == Qt.CheckState.Checked.value or value == Qt.CheckState.Checked:
            self._selected_paths.add(key)
        else:
            self._selected_paths.discard(key)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
        self.selectionChanged.emit(len(self._selected_paths))
        return True

    def set_documents(self, documents: Iterable[DocumentCandidate]) -> None:
        ordered = sorted(
            documents,
            key=lambda item: (
                (item.person or "").casefold(),
                normalized_path(item.source),
            ),
        )
        available = {normalized_path(item.source) for item in ordered}
        self.beginResetModel()
        self._documents = ordered
        self._selected_paths.intersection_update(available)
        self.endResetModel()
        self.selectionChanged.emit(len(self._selected_paths))

    def set_selected_rows(self, rows: Iterable[int], selected: bool) -> None:
        changed_rows: list[int] = []
        for row in rows:
            if not 0 <= row < len(self._documents):
                continue
            key = normalized_path(self._documents[row].source)
            before = key in self._selected_paths
            if selected:
                self._selected_paths.add(key)
            else:
                self._selected_paths.discard(key)
            if before != selected:
                changed_rows.append(row)
        for row in changed_rows:
            index = self.index(row, self.CHECK_COLUMN)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
        if changed_rows:
            self.selectionChanged.emit(len(self._selected_paths))

    def is_selected(self, row: int) -> bool:
        return normalized_path(self._documents[row].source) in self._selected_paths

    def selected_documents(self) -> tuple[DocumentCandidate, ...]:
        return tuple(
            document
            for document in self._documents
            if normalized_path(document.source) in self._selected_paths
        )

    @property
    def documents(self) -> tuple[DocumentCandidate, ...]:
        return tuple(self._documents)

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / 1024 / 1024:.1f} MB"

    @staticmethod
    def _waiting_text(modified_ns: int) -> str:
        modified = datetime.fromtimestamp(modified_ns / 1_000_000_000, timezone.utc)
        seconds = max(0, int((datetime.now(timezone.utc) - modified).total_seconds()))
        if seconds < 60:
            return "meno di un minuto"
        if seconds < 3600:
            return f"{seconds // 60} min"
        if seconds < 86400:
            return f"{seconds // 3600} h"
        return f"{seconds // 86400} g"

    @staticmethod
    def _sort_value(document: DocumentCandidate, column: int):
        if column == DocumentTableModel.DOCUMENT_COLUMN:
            return document.source.name.casefold()
        if column == DocumentTableModel.PERSON_COLUMN:
            return (document.person or "").casefold()
        if column == DocumentTableModel.WAITING_COLUMN:
            return document.modified_ns
        if column == DocumentTableModel.SIZE_COLUMN:
            return document.size
        return normalized_path(document.source)
