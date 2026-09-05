from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path

from PySide6.QtCore import QThreadPool

from mfirma.batch import BatchOrchestrator
from mfirma.config import AppConfig, ConfigRepository
from mfirma.models import (
    BatchPhase,
    DocumentCandidate,
    JobStatus,
    NormalizedDisplayRect,
    SignJob,
    SignaturePositionPlan,
)
from mfirma.ui.dialogs import PinDialog
from mfirma.ui.main_window import MFirmaQtWindow
from mfirma.ui.pages import ResultPage
from mfirma.ui.workers import SigningController


def _candidate(path: Path, person: str = "Persona") -> DocumentCandidate:
    path.write_bytes(b"%PDF-fake")
    return DocumentCandidate.from_path(path, person)


class ControlledSession:
    def __init__(
        self,
        *,
        started: threading.Event | None = None,
        release: threading.Event | None = None,
    ):
        self.started = started
        self.release = release
        self.calls = []

    def sign_pdf(
        self,
        source,
        temporary_output,
        *,
        placement=None,
        normalized_rect=None,
        phase_callback=None,
    ):
        self.calls.append((source, placement, normalized_rect))
        if self.started is not None:
            self.started.set()
        if self.release is not None:
            assert self.release.wait(3)
        temporary_output.write_bytes(source.read_bytes() + b"\nSIGNED")
        phase_callback("verifying")


class ControlledProvider:
    def __init__(self, session: ControlledSession | None = None):
        self.session = session or ControlledSession()
        self.received_pins = []

    @contextmanager
    def open(self, pin):
        self.received_pins.append(pin)
        yield self.session


def test_pin_dialog_returns_once_and_clears_the_field(qtbot):
    dialog = PinDialog(2)
    qtbot.addWidget(dialog)
    dialog.pin_edit.setText("segreto-temporaneo")

    assert dialog.take_pin() == "segreto-temporaneo"
    assert dialog.pin_edit.text() == ""
    assert dialog.take_pin() is None

    dialog.pin_edit.setText("da-cancellare")
    dialog.reject()
    assert dialog.pin_edit.text() == ""


def test_protected_middleware_prompt_does_not_collect_a_pin(qtbot):
    dialog = PinDialog(1)
    qtbot.addWidget(dialog)
    dialog.pin_edit.setText("non-usare")
    dialog.protected_prompt.setChecked(True)

    assert not dialog.pin_edit.isEnabled()
    assert dialog.take_pin() is None
    assert dialog.pin_edit.text() == ""


def test_signing_controller_cancels_only_after_current_document(qtbot, workdir):
    first = _candidate(workdir / "primo.pdf")
    second = _candidate(workdir / "secondo.pdf")
    third = _candidate(workdir / "terzo.pdf")
    started = threading.Event()
    release = threading.Event()
    provider = ControlledProvider(ControlledSession(started=started, release=release))
    controller = SigningController(thread_pool=QThreadPool())
    events = []
    cancellation_states = []
    controller.progressChanged.connect(events.append)
    controller.cancellationChanged.connect(cancellation_states.append)
    plan = SignaturePositionPlan(
        placements={},
        shared_rect=NormalizedDisplayRect(0.1, 0.1, 0.35, 0.15),
    )

    with qtbot.waitSignal(controller.batchFinished, timeout=5000) as signal:
        assert controller.start(
            BatchOrchestrator(provider),
            (first, second, third),
            pin="1234-test-only",
            position_plan=plan,
        )
        qtbot.waitUntil(started.is_set, timeout=2000)
        controller.request_cancel()
        release.set()

    jobs = signal.args[0]
    assert [job.status for job in jobs] == [
        JobStatus.SUCCEEDED,
        JobStatus.CANCELLED,
        JobStatus.CANCELLED,
    ]
    assert cancellation_states == [False, True]
    assert provider.received_pins == ["1234-test-only"]
    assert provider.session.calls[0][2] == plan.shared_rect
    first_phases = [
        event.phase for event in events if event.job.document.source == first.source
    ]
    assert first_phases == [
        BatchPhase.CHECKING,
        BatchPhase.SIGNING,
        BatchPhase.VERIFYING,
        BatchPhase.PUBLISHING,
        BatchPhase.COMPLETED,
    ]
    assert controller._worker is None
    assert not hasattr(controller, "pin")


def test_result_page_sanitizes_technical_errors_and_filters_problems(qtbot, workdir):
    succeeded_document = _candidate(workdir / "riuscito.pdf")
    failed_document = _candidate(workdir / "errore.pdf")
    succeeded = SignJob(
        succeeded_document,
        workdir / "riuscito_firmato.pdf",
        status=JobStatus.SUCCEEDED,
    )
    failed = SignJob(
        failed_document,
        workdir / "errore_firmato.pdf",
        status=JobStatus.FAILED,
        error_code="SIGNATURE_FAILED",
        message="token error; PIN 1234-test-only",
    )
    page = ResultPage()
    qtbot.addWidget(page)

    page.set_jobs((succeeded, failed))

    assert page.model.rowCount() == 2
    assert "1234-test-only" not in page.summary_text()
    assert page.model.data(page.model.index(1, 4)) == "La firma non è riuscita."
    page.problems_only.setChecked(True)
    assert page.proxy.rowCount() == 1


def test_main_window_runs_fake_batch_and_shows_real_result(qtbot, workdir):
    document = _candidate(workdir / "documento.pdf")
    repository = ConfigRepository(workdir / "config.json")
    repository.save(AppConfig())
    window = MFirmaQtWindow(repository, auto_scan=False)
    qtbot.addWidget(window)
    window.preview_page.set_documents((document,), "Certificato simulato")
    provider = ControlledProvider()

    with qtbot.waitSignal(window.signing_controller.batchFinished, timeout=5000):
        assert window.start_batch(
            provider,
            SignaturePositionPlan(
                placements={},
                shared_rect=NormalizedDisplayRect(0.1, 0.1, 0.4, 0.15),
            ),
            pin="pin-solo-test",
        )

    assert window.stackedWidget.currentWidget() is window.result_page
    assert window.result_page.model.jobs[0].status is JobStatus.SUCCEEDED
    assert (workdir / "documento_firmato.pdf").read_bytes().endswith(b"SIGNED")
    assert window.progress_page.progress_bar.value() == 1
    assert window.progress_page.succeeded_label.text() == "1"
    assert (
        window.progress_page.progress_bar.accessibleDescription()
        == "1 di 1 documenti completati"
    )
    assert window.wait_for_workers()


def test_close_hides_window_and_tray_exit_finishes_when_idle(qtbot, workdir):
    repository = ConfigRepository(workdir / "config.json")
    repository.save(AppConfig())
    window = MFirmaQtWindow(
        repository,
        tray_available=True,
        auto_scan=False,
    )
    qtbot.addWidget(window)
    window.show()

    window.close()
    assert not window.isVisible()
    assert not window._shutdown_requested

    window.tray_controller.open_action.trigger()
    assert window.isVisible()

    with qtbot.waitSignal(window.shutdownReady, timeout=1000):
        window.tray_controller.exit_action.trigger()
    assert window._shutdown_requested
    assert not window.tray_controller.tray_icon.isVisible()


def test_tray_exit_waits_for_current_signature_then_cancels_rest(qtbot, workdir):
    first = _candidate(workdir / "tray-primo.pdf")
    second = _candidate(workdir / "tray-secondo.pdf")
    started = threading.Event()
    release = threading.Event()
    provider = ControlledProvider(ControlledSession(started=started, release=release))
    repository = ConfigRepository(workdir / "config.json")
    repository.save(AppConfig())
    window = MFirmaQtWindow(
        repository,
        signing_controller=SigningController(thread_pool=QThreadPool()),
        tray_available=True,
        auto_scan=False,
    )
    qtbot.addWidget(window)
    window.preview_page.set_documents((first, second), "Certificato simulato")
    finished_jobs = []
    window.signing_controller.batchFinished.connect(finished_jobs.extend)

    assert window.start_batch(
        provider,
        SignaturePositionPlan(placements={}),
        pin="pin-test-tray",
    )
    qtbot.waitUntil(started.is_set, timeout=2000)
    window.tray_controller.exit_action.trigger()

    assert window._shutdown_requested
    assert window.signing_controller.busy
    assert window.signing_controller._cancel_event.is_set()
    with qtbot.waitSignal(window.shutdownReady, timeout=5000):
        release.set()

    assert [job.status for job in finished_jobs] == [
        JobStatus.SUCCEEDED,
        JobStatus.CANCELLED,
    ]
    assert window.wait_for_workers()
