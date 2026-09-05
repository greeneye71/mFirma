from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Iterable

from PySide6.QtCore import QTimer, Qt, Signal
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
from ..state import DeviceState, ScanState, normalized_path


class _StatusPanel(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(3)
        caption = BodyLabel(title, self)
        caption.setStyleSheet("color: #667085;")
        self.value = SubtitleLabel("—", self)
        self.detail = BodyLabel("", self)
        self.detail.setWordWrap(True)
        layout.addWidget(caption)
        layout.addWidget(self.value)
        layout.addWidget(self.detail)

    def set_status(self, value: str, detail: str = "") -> None:
        self.value.setText(value)
        self.detail.setText(detail)


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
        self.refresh_button = PushButton("Aggiorna", self)
        header.addWidget(self.add_button)
        header.addWidget(self.refresh_button)
        root.addLayout(header)

        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        self.folder_status = _StatusPanel("Cartella", self)
        self.folder_status.setObjectName("folderStatus")
        self.device_status = _StatusPanel("Dispositivo", self)
        self.device_status.setObjectName("deviceStatus")
        self.certificate_status = _StatusPanel("Certificato", self)
        self.certificate_status.setObjectName("certificateStatus")
        for panel in (self.folder_status, self.device_status, self.certificate_status):
            panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            status_row.addWidget(panel)
        root.addLayout(status_row)

        content = QHBoxLayout()
        content.setSpacing(12)
        people_box = QVBoxLayout()
        people_box.addWidget(SubtitleLabel("Persone", self))
        self.people_list = QListWidget(self)
        self.people_list.setObjectName("peopleFilter")
        self.people_list.setFixedWidth(190)
        people_box.addWidget(self.people_list, 1)
        content.addLayout(people_box)

        documents_box = QVBoxLayout()
        self.search = SearchLineEdit(self)
        self.search.setObjectName("documentSearch")
        self.search.setPlaceholderText("Cerca documento, persona o percorso")
        self.search.setAccessibleName("Cerca documenti")
        documents_box.addWidget(self.search)

        self.table = QTableView(self)
        self.table.setObjectName("documentTable")
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(DocumentTableModel.PERSON_COLUMN, Qt.SortOrder.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(DocumentTableModel.CHECK_COLUMN, 42)
        self.table.setColumnWidth(DocumentTableModel.DOCUMENT_COLUMN, 360)
        self.table.setColumnWidth(DocumentTableModel.PERSON_COLUMN, 180)
        self.table.setColumnWidth(DocumentTableModel.WAITING_COLUMN, 120)
        self.table.setColumnWidth(DocumentTableModel.SIZE_COLUMN, 100)
        documents_box.addWidget(self.table, 1)

        self.empty_label = QLabel("Non ci sono PDF da firmare", self)
        self.empty_label.setObjectName("emptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #667085; padding: 12px;")
        documents_box.addWidget(self.empty_label)
        content.addLayout(documents_box, 1)
        root.addLayout(content, 1)

        self.warning_label = BodyLabel("", self)
        self.warning_label.setObjectName("scanWarning")
        self.warning_label.setWordWrap(True)
        self.warning_label.hide()
        root.addWidget(self.warning_label)

        selection_bar = QHBoxLayout()
        self.select_visible_button = PushButton("Seleziona risultati visibili", self)
        self.selection_label = BodyLabel("0 documenti selezionati", self)
        self.summary_label = BodyLabel("Ultima pagina · Basso a destra", self)
        self.prepare_button = PrimaryPushButton("Prepara la firma", self)
        self.prepare_button.setObjectName("prepareButton")
        self.prepare_button.setEnabled(False)
        selection_bar.addWidget(self.select_visible_button)
        selection_bar.addWidget(self.selection_label)
        selection_bar.addStretch(1)
        selection_bar.addWidget(self.summary_label)
        selection_bar.addWidget(self.prepare_button)
        root.addLayout(selection_bar)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)

        self._refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        self._find_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self._select_all_shortcut = QShortcut(QKeySequence("Ctrl+A"), self.table)

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

    def merge_documents(self, documents: Iterable[DocumentCandidate]) -> None:
        merged = {
            normalized_path(document.source): document
            for document in self.model.documents
        }
        for document in documents:
            merged[normalized_path(document.source)] = document
        self.set_documents(ScanResult(tuple(merged.values()), {}))

    def set_scan_state(
        self,
        state: ScanState,
        *,
        total: int | None = None,
        errors: tuple[str, ...] = (),
    ) -> None:
        if state is ScanState.SCANNING:
            self.folder_status.set_status("Scansione in corso", "Attendere l'aggiornamento")
            self.refresh_button.setEnabled(False)
        elif state is ScanState.UNAVAILABLE:
            self.folder_status.set_status(
                "Non raggiungibile", "L'ultima lista disponibile rimane visibile"
            )
            self.refresh_button.setEnabled(True)
        elif state is ScanState.AVAILABLE_WITH_WARNINGS:
            self.folder_status.set_status(f"{total or 0} PDF", "Disponibile con avvisi")
            self.refresh_button.setEnabled(True)
        elif state is ScanState.AVAILABLE:
            self.folder_status.set_status(f"{total or 0} PDF", "Cartella disponibile")
            self.refresh_button.setEnabled(True)
        else:
            self.folder_status.set_status("Da aggiornare")
            self.refresh_button.setEnabled(True)
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

    def set_device_status(
        self,
        state: DeviceState,
        *,
        token_label: str = "",
        certificate_label: str = "",
    ) -> None:
        if state is DeviceState.READY:
            self.device_status.set_status(token_label or "Dispositivo configurato")
        elif state is DeviceState.MISSING:
            self.device_status.set_status("Non disponibile", "Collega il dispositivo")
        elif state is DeviceState.MIDDLEWARE_ERROR:
            self.device_status.set_status("Middleware non disponibile")
        else:
            self.device_status.set_status("Da verificare")
        if certificate_label:
            self.certificate_status.set_status(certificate_label, "Configurato")
        else:
            self.certificate_status.set_status("Non configurato")

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
        self.proxy.set_person_filter(person)
        self._update_empty_state()

    def _apply_search(self) -> None:
        self.proxy.set_search_text(self.search.text())
        self._update_empty_state()

    def _selection_changed(self, count: int) -> None:
        suffix = "documento selezionato" if count == 1 else "documenti selezionati"
        self.selection_label.setText(f"{count} {suffix}")
        self.prepare_button.setEnabled(count > 0)

    def _update_empty_state(self) -> None:
        visible = self.proxy.rowCount() == 0
        self.empty_label.setVisible(visible)
        self.table.setVisible(not visible)

    def _prepare(self) -> None:
        selected = self.model.selected_documents()
        if selected:
            self.prepareRequested.emit(selected)
