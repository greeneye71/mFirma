from __future__ import annotations

import threading
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QThreadPool, Qt
from qfluentwidgets import NavigationBarPushButton

from mfirma.config import AppConfig, ConfigRepository
from mfirma.models import DocumentCandidate
from mfirma.scanner import ScanResult
from mfirma.ui.main_window import MFirmaQtWindow
from mfirma.ui.pages.queue_page import QueuePage
from mfirma.ui.state import ScanState
from mfirma.ui.workers import FileImportController, ScanController


def _candidate(path: Path, person: str) -> DocumentCandidate:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-test")
    return DocumentCandidate.from_path(path, person)


def test_queue_page_filters_with_debounce_and_selects_visible(qtbot, workdir):
    page = QueuePage()
    qtbot.addWidget(page)
    documents = (
        _candidate(workdir / "Mario" / "contratto.pdf", "Mario"),
        _candidate(workdir / "Lucia" / "referto.pdf", "Lucia"),
    )
    page.set_documents(ScanResult(documents, {"Mario": 1, "Lucia": 1}))

    assert not page.prepare_button.isEnabled()
    page.search.setText("referto")
    qtbot.wait(250)
    assert page.proxy.rowCount() == 1
    page.select_all_visible()
    assert page.prepare_button.isEnabled()
    assert page.model.selected_documents() == (documents[1],)

    page.search.clear()
    qtbot.wait(250)
    assert page.proxy.rowCount() == 2
    assert page.model.selected_documents() == (documents[1],)


def test_queue_page_keeps_last_snapshot_when_network_is_unavailable(qtbot, workdir):
    page = QueuePage()
    qtbot.addWidget(page)
    page.show()
    document = _candidate(workdir / "Mario" / "uno.pdf", "Mario")
    page.set_documents(ScanResult((document,), {"Mario": 1}))

    page.set_scan_error("percorso non trovato")

    assert page.model.rowCount() == 1
    assert page.folder_status.value.text() == "Non raggiungibile"
    assert page.warning_label.isVisible()
    assert "non è raggiungibile" in page.warning_label.text()


def test_queue_keyboard_actions_and_accessible_names(qtbot, workdir):
    page = QueuePage()
    qtbot.addWidget(page)
    document = _candidate(workdir / "Mario" / "tastiera.pdf", "Mario")
    page.set_documents(ScanResult((document,), {"Mario": 1}))
    page.resize(1000, 700)
    page.show()
    page.activateWindow()
    qtbot.wait(10)
    page.table.setFocus()
    page.table.selectRow(0)
    page.table.setCurrentIndex(page.proxy.index(0, 1))

    qtbot.keyClick(page.table, Qt.Key.Key_Space)
    assert page.model.selected_documents() == (document,)

    prepared = []
    page.prepareRequested.connect(prepared.append)
    qtbot.keyClick(page.table, Qt.Key.Key_Return)
    assert prepared == [(document,)]

    qtbot.keyClick(page.table, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    assert page.search.hasFocus()
    assert page.table.accessibleName() == "Documenti da firmare"
    assert page.prepare_button.accessibleName().startswith("Prepara la firma")

    with qtbot.waitSignal(page.refreshRequested, timeout=1000):
        qtbot.keyClick(page.search, Qt.Key.Key_F5)


def test_scan_controller_runs_scanner_outside_gui_thread(qtbot, workdir):
    gui_thread = threading.current_thread()
    called_from = []

    def fake_scanner(_root, **_options):
        called_from.append(threading.current_thread())
        return ScanResult((), {})

    pool = QThreadPool()
    controller = ScanController(scanner=fake_scanner, thread_pool=pool)

    with qtbot.waitSignal(controller.scanSucceeded, timeout=3000):
        assert controller.start(
            workdir,
            recursive=True,
            stability_seconds=0,
            output_suffix="_firmato",
        )
        assert not controller.start(
            workdir,
            recursive=True,
            stability_seconds=0,
            output_suffix="_firmato",
        )

    assert called_from[0] is not gui_thread
    assert controller.busy is False


def test_fluent_window_smoke_and_real_scan(qtbot, workdir):
    _candidate(workdir / "Mario" / "uno.pdf", "Mario")
    _candidate(workdir / "Lucia" / "due.pdf", "Lucia")
    config = AppConfig()
    config.monitor.root = str(workdir)
    config.monitor.stability_seconds = 0
    repository = ConfigRepository(workdir / "config.json")
    repository.save(config)
    pool = QThreadPool()
    controller = ScanController(thread_pool=pool)
    window = MFirmaQtWindow(
        repository,
        scan_controller=controller,
        auto_scan=False,
    )
    qtbot.addWidget(window)
    window.show()

    with qtbot.waitSignal(controller.scanSucceeded, timeout=3000):
        window.refresh_documents()

    assert window.queue_page.model.rowCount() == 2
    assert window.queue_page.objectName() == "queuePage"
    assert window.history_page.objectName() == "historyPage"
    assert window.settings_page.objectName() == "settingsPage"
    navigation_labels = {
        button.text() for button in window.findChildren(NavigationBarPushButton)
    }
    assert "Cronologia" in navigation_labels
    assert "Impostazioni" in navigation_labels
    assert any(label.startswith("Da firmare") for label in navigation_labels)
    assert window.minimumWidth() == 900
    assert window.minimumHeight() == 620
    assert window.wait_for_workers()


def test_module_entry_point_routes_qt_by_default(monkeypatch):
    import mfirma.__main__ as entry_point
    import mfirma.ui.application as qt_application

    calls: list[list[str]] = []
    monkeypatch.setattr(sys, "argv", ["mfirma"])
    monkeypatch.setattr(
        qt_application,
        "run_application",
        lambda arguments: calls.append(list(arguments)) or 0,
    )

    with pytest.raises(SystemExit) as exit_info:
        entry_point.main()

    assert exit_info.value.code == 0
    assert calls == [["mfirma"]]


def test_external_pdf_selection_is_imported_off_thread_and_selected(qtbot, workdir):
    first = _candidate(workdir / "uno.pdf", "")
    second = _candidate(workdir / "due.pdf", "")
    pool = QThreadPool()
    importer = FileImportController(thread_pool=pool)
    repository = ConfigRepository(workdir / "config.json")
    repository.save(AppConfig())
    window = MFirmaQtWindow(
        repository,
        import_controller=importer,
        tray_available=False,
        auto_scan=False,
    )
    qtbot.addWidget(window)

    with qtbot.waitSignal(importer.importSucceeded, timeout=3000):
        window.receive_external_paths((first.source, second.source))

    assert len(window.queue_page.model.documents) == 2
    assert len(window.queue_page.model.selected_documents()) == 2
    assert window.queue_page.prepare_button.isEnabled()
    assert window.wait_for_workers()
