from __future__ import annotations

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel

from .document_table_model import DocumentTableModel


class DocumentFilterModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._person: str | None = None
        self._search_text = ""
        self.setDynamicSortFilter(True)
        self.setSortRole(DocumentTableModel.SORT_ROLE)

    def set_person_filter(self, person: str | None) -> None:
        self._person = person or None
        self._refilter()

    def set_search_text(self, text: str) -> None:
        self._search_text = " ".join(text.casefold().replace("\\", "/").split())
        self._refilter()

    def _refilter(self) -> None:
        self.beginFilterChange()
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        model = self.sourceModel()
        if not isinstance(model, DocumentTableModel):
            return False
        index = model.index(source_row, DocumentTableModel.DOCUMENT_COLUMN, source_parent)
        document = model.data(index, DocumentTableModel.DOCUMENT_ROLE)
        if document is None:
            return False
        if self._person and (document.person or "Senza persona") != self._person:
            return False
        if not self._search_text:
            return True
        searchable = " ".join(
            (
                document.source.name,
                document.person or "",
                str(document.source),
            )
        ).casefold().replace("\\", "/")
        return self._search_text in searchable
