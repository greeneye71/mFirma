from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Iterable

from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    PrimaryPushButton,
    PushButton,
    SearchLineEdit,
    SubtitleLabel,
    TitleLabel,
)

from ...models import DocumentCandidate
from ...scanner import ScanResult
from ..models import DocumentFilterModel, DocumentTableModel
from ..state import ScanState, normalized_path


class QueuePage(QWidget):
    refreshRequested = Signal()
    addFilesRequested = Signal()
    prepareRequested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("queuePage")
        self.model = DocumentTableModel(self)
        self.proxy = DocumentFilterModel(self)
        self.proxy.setSourceModel(self.model)
        self._active_person: str | None = None
        self._mode = "folder"
        self._root_path = ""
        self._build_ui()
        self._connect_ui()
        self.set_scan_state(ScanState.IDLE)
        self._update_empty_state()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_box.addWidget(TitleLabel("Documenti da firmare", self))
        self.updated_label = BodyLabel("Non ancora aggiornato", self)
        title_box.addWidget(self.updated_label)
        header.addLayout(title_box)
        header.addStretch(1)
        self.add_button = PushButton("Aggiungi PDF", self)
        self.add_button.setAccessibleName("Aggiungi documenti PDF")
        self.refresh_button = PushButton("Aggiorna", self)
        self.refresh_button.setAccessibleName("Aggiorna cartella")
        header.addWidget(self.add_button)
        header.addWidget(self.refresh_button)
        root.addLayout(header)

        self.folder_path_label = BodyLabel("Cartella non configurata", self)
        self.folder_path_label.setWordWrap(True)
        self.folder_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.folder_path_label)

        content = QHBoxLayout()
        content.setSpacing(12)
        self.people_panel = QWidget(self)
        people_box = QVBoxLayout(self.people_panel)
        people_box.setContentsMargins(0, 0, 0, 0)
        people_box.addWidget(SubtitleLabel("Sottocartelle", self))
        self.people_list = QListWidget(self)
        self.people_list.setObjectName("peopleFilter")
        self.people_list.setAccessibleName("Filtro per persona")
        self.people_list.setFixedWidth(190)
        people_box.addWidget(self.people_list, 1)
        content.addWidget(self.people_panel)

        documents_box = QVBoxLayout()
        self.search = SearchLineEdit(self)
        self.search.setObjectName("documentSearch")
        self.search.setPlaceholderText("Cerca documento, persona o percorso")
        self.search.setAccessibleName("Cerca documenti")
        documents_box.addWidget(self.search)

        self.table = QTableView(self)
        self.table.setObjectName("documentTable")
        self.table.setAccessibleName("Documenti da firmare")
        self.table.setAccessibleDescription(
            "Usa Spazio per selezionare le righe evidenziate e Invio per preparare la firma"
        )
        self.table.installEventFilter(self)
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(DocumentTableModel.PERSON_COLUMN, Qt.SortOrder.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableView::item:selected { background-color: #245CB5; color: white; }
            QTableView::item:selected:!active { background-color: #245CB5; color: white; }
        """)
        self.people_list.setStyleSheet("""
            QListWidget::item { padding: 6px; }
            QListWidget::item:selected { background-color: #245CB5; color: white; border-radius: 4px; }
            QListWidget::item:selected:!active { background-color: #245CB5; color: white; }
        """)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(DocumentTableModel.CHECK_COLUMN, 42)
        self.table.setColumnWidth(DocumentTableModel.DOCUMENT_COLUMN, 360)
        self.table.setColumnWidth(DocumentTableModel.PERSON_COLUMN, 180)
        self.table.setColumnWidth(DocumentTableModel.WAITING_COLUMN, 120)
        self.table.setColumnWidth(DocumentTableModel.SIZE_COLUMN, 100)
        documents_box.addWidget(self.table, 1)

        self.empty_label = QLabel("Non ci sono PDF da firmare", self)
        self.empty_label.setObjectName("emptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setContentsMargins(12, 12, 12, 12)
        documents_box.addWidget(self.empty_label)
        content.addLayout(documents_box, 1)
        root.addLayout(content, 1)

        self.warning_label = BodyLabel("", self)
        self.warning_label.setObjectName("scanWarning")
        self.warning_label.setWordWrap(True)
        self.warning_label.hide()
        root.addWidget(self.warning_label)

        selection_bar = QHBoxLayout()
        self.select_visible_button = PushButton("Seleziona tutti", self)
        self.select_visible_button.setAccessibleName(
            "Seleziona o deseleziona tutti i risultati visibili"
        )
        self.prepare_button = PrimaryPushButton("Prepara la firma", self)
        self.prepare_button.setObjectName("prepareButton")
        self.prepare_button.setAccessibleName("Prepara la firma dei documenti selezionati")
        self.prepare_button.setEnabled(False)
        selection_bar.addWidget(self.select_visible_button)
        selection_bar.addStretch(1)
        selection_bar.addWidget(self.prepare_button)
        root.addLayout(selection_bar)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)

        self._refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        self._find_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self._select_all_shortcut = QShortcut(QKeySequence("Ctrl+A"), self.table)
        self._select_all_shortcut.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        QWidget.setTabOrder(self.add_button, self.refresh_button)
        QWidget.setTabOrder(self.refresh_button, self.people_list)
        QWidget.setTabOrder(self.people_list, self.search)
        QWidget.setTabOrder(self.search, self.table)
        QWidget.setTabOrder(self.table, self.select_visible_button)
        QWidget.setTabOrder(self.select_visible_button, self.prepare_button)

    def _connect_ui(self) -> None:
        self.refresh_button.clicked.connect(self.refreshRequested)
        self.add_button.clicked.connect(self.addFilesRequested)
        self.search.textChanged.connect(lambda _text: self._search_timer.start())
        self._search_timer.timeout.connect(self._apply_search)
        self.people_list.currentItemChanged.connect(self._person_changed)
        self.select_visible_button.clicked.connect(self.select_all_visible)
        self.model.selectionChanged.connect(self._selection_changed)
        self.prepare_button.clicked.connect(self._prepare)
        self._refresh_shortcut.activated.connect(self.refreshRequested)
        self._find_shortcut.activated.connect(self.search.setFocus)
        self._select_all_shortcut.activated.connect(self.select_all_visible)
        self.table.doubleClicked.connect(lambda _index: self._prepare_from_table())

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is self.table and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Space:
                self.toggle_highlighted_rows()
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._prepare_from_table()
                return True
        return super().eventFilter(watched, event)

    def set_documents(self, result: ScanResult) -> None:
        self.model.set_documents(result.documents)
        self._rebuild_people(result.documents)
        state = (
            ScanState.AVAILABLE_WITH_WARNINGS
            if result.errors
            else ScanState.AVAILABLE
        )
        self.set_scan_state(state, total=result.total, errors=result.errors)
        self.updated_label.setText(
            f"Aggiornato il {datetime.now().astimezone():%d/%m/%Y alle %H:%M:%S}"
        )
        self._update_empty_state()

    def merge_documents(
        self, documents: Iterable[DocumentCandidate], *, select: bool = False
    ) -> None:
        imported = tuple(documents)
        merged = {
            normalized_path(document.source): document
            for document in self.model.documents
        }
        for document in imported:
            merged[normalized_path(document.source)] = document
        self.set_documents(ScanResult(tuple(merged.values()), {}))
        if select:
            imported_paths = {
                normalized_path(document.source) for document in imported
            }
            rows = [
                row
                for row, document in enumerate(self.model.documents)
                if normalized_path(document.source) in imported_paths
            ]
            self.model.set_selected_rows(rows, True)

    def set_scan_state(
        self,
        state: ScanState,
        *,
        total: int | None = None,
        errors: tuple[str, ...] = (),
    ) -> None:
        self.refresh_button.setEnabled(state is not ScanState.SCANNING)
        if state is ScanState.SCANNING:
            self.updated_label.setText("Scansione in corso…")
        self.warning_label.setVisible(bool(errors))
        if errors:
            self.warning_label.setText(
                f"Scansione completata con {len(errors)} elementi non leggibili."
            )

    def set_scan_error(self, _technical_message: str) -> None:
        self.set_scan_state(ScanState.UNAVAILABLE)
        self.warning_label.setText(
            "La cartella non è raggiungibile. Controlla la rete e premi Aggiorna."
        )
        self.warning_label.show()

    def configure_mode(self, mode: str, root_path: str) -> None:
        changed = mode != self._mode or root_path != self._root_path
        self._mode, self._root_path = mode, root_path
        manual = mode == "manual"
        self.people_panel.setVisible(not manual)
        self.refresh_button.setVisible(not manual)
        self._refresh_shortcut.setEnabled(not manual)
        self.folder_path_label.setVisible(not manual)
        self.table.setColumnHidden(DocumentTableModel.PERSON_COLUMN, manual)
        if changed:
            self.model.set_documents(())
            self._rebuild_people(())
            self.updated_label.setText("Aggiungi i PDF da firmare" if manual else "Da aggiornare")
            self.warning_label.hide()
            self._update_empty_state()
        self._update_folder_path()

    def show_warning(self, message: str) -> None:
        self.warning_label.setText(message)
        self.warning_label.show()

    def _update_folder_path(self) -> None:
        from pathlib import Path

        root = Path(self._root_path) if self._root_path else None
        path = root / self._active_person if root and self._active_person else root
        self.folder_path_label.setText(str(path) if path else "Cartella non configurata")

    def visible_source_rows(self) -> list[int]:
        rows: list[int] = []
        for proxy_row in range(self.proxy.rowCount()):
            proxy_index = self.proxy.index(proxy_row, DocumentTableModel.DOCUMENT_COLUMN)
            rows.append(self.proxy.mapToSource(proxy_index).row())
        return rows

    def select_all_visible(self) -> None:
        rows = self.visible_source_rows()
        if not rows:
            return
        select = not all(self.model.is_selected(row) for row in rows)
        self.model.set_selected_rows(rows, select)

    def toggle_highlighted_rows(self) -> None:
        selection = self.table.selectionModel()
        proxy_rows = {index.row() for index in selection.selectedRows()}
        if not proxy_rows and self.table.currentIndex().isValid():
            proxy_rows.add(self.table.currentIndex().row())
        source_rows = [
            self.proxy.mapToSource(
                self.proxy.index(row, DocumentTableModel.DOCUMENT_COLUMN)
            ).row()
            for row in sorted(proxy_rows)
        ]
        if not source_rows:
            return
        select = not all(self.model.is_selected(row) for row in source_rows)
        self.model.set_selected_rows(source_rows, select)

    def _prepare_from_table(self) -> None:
        if not self.model.selected_documents():
            current = self.table.currentIndex()
            if current.isValid():
                source = self.proxy.mapToSource(current)
                self.model.set_selected_rows((source.row(),), True)
        self._prepare()

    def _rebuild_people(self, documents: Iterable[DocumentCandidate]) -> None:
        active = self._active_person
        counts = Counter(document.person or "Senza persona" for document in documents)
        self.people_list.blockSignals(True)
        self.people_list.clear()
        all_item = QListWidgetItem(f"Tutti ({sum(counts.values())})")
        all_item.setData(Qt.ItemDataRole.UserRole, None)
        self.people_list.addItem(all_item)
        active_row = 0
        for row, (person, count) in enumerate(sorted(counts.items()), start=1):
            item = QListWidgetItem(f"{person} ({count})")
            item.setData(Qt.ItemDataRole.UserRole, person)
            self.people_list.addItem(item)
            if person == active:
                active_row = row
        self.people_list.setCurrentRow(active_row)
        self.people_list.blockSignals(False)
        selected = self.people_list.currentItem()
        self._person_changed(selected, None)

    def _person_changed(self, current: QListWidgetItem | None, _previous) -> None:
        person = current.data(Qt.ItemDataRole.UserRole) if current else None
        self._active_person = person
        self._update_folder_path()
        self.proxy.set_person_filter(person)
        self._update_empty_state()

    def _apply_search(self) -> None:
        self.proxy.set_search_text(self.search.text())
        self._update_empty_state()

    def _selection_changed(self, count: int) -> None:
        suffix = "documento" if count == 1 else "documenti"
        self.prepare_button.setText(f"Prepara la firma · {count} {suffix}" if count else "Prepara la firma")
        self.prepare_button.setEnabled(count > 0)

    def _update_empty_state(self) -> None:
        visible = self.proxy.rowCount() == 0
        self.empty_label.setVisible(visible)
        self.table.setVisible(not visible)

    def _prepare(self) -> None:
        selected = self.model.selected_documents()
        if selected:
            self.prepareRequested.emit(selected)
