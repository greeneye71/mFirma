from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt

from mfirma.models import DocumentCandidate
from mfirma.ui.models import DocumentFilterModel, DocumentTableModel


def _document(index: int, *, person: str = "Mario") -> DocumentCandidate:
    return DocumentCandidate(
        Path(f"C:/documenti/{person}/documento-{index:04d}.pdf"),
        person,
        1024 + index,
        time.time_ns() - index * 1_000_000_000,
    )


def test_table_model_handles_1000_documents_and_stable_path_selection(qtbot):
    model = DocumentTableModel()
    documents = [_document(index, person=f"Persona {index % 20:02d}") for index in range(1000)]
    model.set_documents(reversed(documents))

    assert model.rowCount() == 1000
    first = model.index(0, DocumentTableModel.CHECK_COLUMN)
    assert model.setData(first, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
    selected_path = model.selected_documents()[0].source

    proxy = DocumentFilterModel()
    proxy.setSourceModel(model)
    proxy.sort(DocumentTableModel.SIZE_COLUMN, Qt.SortOrder.DescendingOrder)
    proxy.set_person_filter("Persona 00")

    assert proxy.rowCount() == 50
    assert model.selected_documents()[0].source == selected_path


def test_filter_matches_person_name_and_path_case_insensitively():
    model = DocumentTableModel()
    model.set_documents(
        (
            _document(1, person="Mario Rossi"),
            _document(2, person="Lucia Bianchi"),
        )
    )
    proxy = DocumentFilterModel()
    proxy.setSourceModel(model)

    proxy.set_search_text("LUCIA")
    assert proxy.rowCount() == 1
    proxy.set_search_text("documento-0001")
    assert proxy.rowCount() == 1
    proxy.set_search_text("C:/DOCUMENTI/MARIO")
    assert proxy.rowCount() == 1
    proxy.set_search_text("")
    proxy.set_person_filter("Mario Rossi")
    assert proxy.rowCount() == 1


def test_replacing_documents_drops_only_missing_selections():
    first = _document(1)
    second = _document(2)
    model = DocumentTableModel()
    model.set_documents((first, second))
    model.set_selected_rows((0, 1), True)

    model.set_documents((second, _document(3)))

    assert model.selected_documents() == (second,)
