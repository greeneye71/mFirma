from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

from mfirma.history import BatchHistoryRecord, HistoryRepository
from mfirma.models import DocumentCandidate, JobStatus, SignJob
from mfirma.ui.pages.history_page import HistoryPage
from mfirma.ui.workers import HistoryController


def _record(workdir, name: str, status: JobStatus) -> BatchHistoryRecord:
    source = workdir / name
    source.write_bytes(b"%PDF-fake")
    job = SignJob(
        DocumentCandidate.from_path(source, "Persona"),
        workdir / f"{source.stem}_firmato.pdf",
        status=status,
        error_code="SIGNATURE_FAILED" if status is JobStatus.FAILED else None,
    )
    return BatchHistoryRecord.from_jobs(
        (job,),
        certificate_label="Certificato prova",
        created_at=datetime(2026, 9, 6, 15, 30, tzinfo=timezone.utc),
    )


def test_history_page_shows_real_records_details_and_copies_id(qtbot, workdir):
    succeeded = _record(workdir, "riuscito.pdf", JobStatus.SUCCEEDED)
    failed = _record(workdir, "errore.pdf", JobStatus.FAILED)
    page = HistoryPage()
    qtbot.addWidget(page)
    page.show()

    page.set_records((failed, succeeded))

    assert page.model.rowCount() == 2
    assert page.model.data(page.model.index(0, 1)) == "Certificato prova"
    assert page.model.data(page.model.index(0, 3)) == "Con segnalazioni"
    assert page.job_model.rowCount() == 1
    assert page.job_model.data(page.job_model.index(0, 4)) == "La firma non è riuscita."
    page.table.selectRow(1)
    assert page.job_model.data(page.job_model.index(0, 0)) == "riuscito.pdf"
    page.copy_id_button.click()
    assert QApplication.clipboard().text() == succeeded.batch_id


def test_history_controller_loads_and_appends_off_thread(qtbot, workdir):
    repository = HistoryRepository(workdir / "history.json")
    pool = QThreadPool()
    pool.setMaxThreadCount(1)
    controller = HistoryController(repository, thread_pool=pool)
    record = _record(workdir, "documento.pdf", JobStatus.SUCCEEDED)

    with qtbot.waitSignal(controller.historyChanged, timeout=3000) as saved:
        controller.append(record)
    assert saved.args == [(record,)]

    with qtbot.waitSignal(controller.historyChanged, timeout=3000) as loaded:
        controller.load()
    assert loaded.args == [(record,)]
    assert not controller.busy
    assert controller.wait_for_done()
