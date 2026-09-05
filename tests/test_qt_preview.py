from __future__ import annotations

import threading
from datetime import datetime, timezone

import pytest
from PySide6.QtCore import QPoint, Qt, QThreadPool
from PySide6.QtPdfWidgets import QPdfView
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from mfirma.appearance import (
    ReportLabSignatureAppearanceRenderer,
    SignatureAppearanceData,
    SignatureAppearanceVariant,
)
from mfirma.config import SignatureConfig
from mfirma.config import AppConfig, ConfigRepository
from mfirma.models import DisplayRect, DocumentCandidate
from mfirma.pdf_service import read_last_page_geometry
from mfirma.placement import display_page_size
from mfirma.ui.pages.preview_page import PreviewPage
from mfirma.ui.main_window import MFirmaQtWindow
from mfirma.ui.workers import (
    PreviewController,
    PreviewIdentity,
    PreviewResult,
    preview_appearance_data,
)


def _pdf(path, *, rotation: int = 0, pages: int = 2):
    pdf = canvas.Canvas(str(path), pagesize=(420, 595))
    for number in range(1, pages + 1):
        pdf.drawString(48, 540, f"Documento di prova — pagina {number}")
        pdf.showPage()
    pdf.save()
    reader = PdfReader(path)
    writer = PdfWriter()
    for page in reader.pages:
        page.cropbox.lower_left = (10, 20)
        page.cropbox.upper_right = (410, 575)
        if rotation:
            page.rotate(rotation)
        writer.add_page(page)
    with path.open("wb") as stream:
        writer.write(stream)
    return DocumentCandidate.from_path(path, "Persona")


def _result(document, workdir, *, rotation: int | None = None) -> PreviewResult:
    geometry, page_index, page_count = read_last_page_geometry(document.source)
    if rotation is not None:
        assert geometry.rotation == rotation
    signature = SignatureConfig()
    data = SignatureAppearanceData(
        signer_name="Giovanni Bergamaschi",
        signing_time=datetime(2026, 9, 5, 15, 30, tzinfo=timezone.utc),
        issuer_name="CA Prova",
    )
    renderer = ReportLabSignatureAppearanceRenderer(workdir)
    with renderer.render_pdf(
        data,
        width_points=signature.width_points,
        height_points=signature.height_points,
        variant=SignatureAppearanceVariant.COMPLETE,
    ) as appearance:
        appearance_pdf = appearance.read_bytes()
    return PreviewResult(
        document=document,
        geometry=geometry,
        page_index=page_index,
        page_count=page_count,
        appearance_pdf=appearance_pdf,
        appearance_data=data,
        signature=signature,
    )


def test_preview_identity_uses_public_certificate_names():
    data = preview_appearance_data(
        PreviewIdentity(
            certificate_label="Etichetta fallback",
            subject="CN=Giovanni Bergamaschi,OU=Direzione,O=Azienda Sanitaria",
            issuer="CN=CA Qualificata,O=Emittente",
        ),
        signing_time=datetime.now(timezone.utc),
        signature_number=2,
        reason="Approvazione",
        location="Roma",
    )

    assert data.signer_name == "Giovanni Bergamaschi"
    assert data.organization == "Azienda Sanitaria"
    assert data.role == "Direzione"
    assert data.issuer_name == "CA Qualificata"
    assert data.signature_number == 2


def test_preview_controller_runs_outside_gui_thread_and_cleans_appearance(
    qtbot, workdir
):
    document = _pdf(workdir / "documento.pdf")
    renderer_directory = workdir / "appearance"
    controller = PreviewController(
        thread_pool=QThreadPool(),
        renderer=ReportLabSignatureAppearanceRenderer(renderer_directory),
    )
    gui_thread = threading.current_thread()
    worker_threads = []
    original = controller._renderer.render_pdf

    def recording_renderer(*args, **kwargs):
        worker_threads.append(threading.current_thread())
        return original(*args, **kwargs)

    controller._renderer.render_pdf = recording_renderer
    results: list[PreviewResult] = []
    controller.previewSucceeded.connect(results.append)

    with qtbot.waitSignal(controller.previewSucceeded, timeout=5000):
        assert controller.prepare(
            document,
            SignatureConfig(),
            PreviewIdentity(certificate_label="Certificato di firma"),
        )
        assert not controller.prepare(
            document, SignatureConfig(), PreviewIdentity()
        )

    assert worker_threads[0] is not gui_thread
    assert results[0].page_index == 1
    assert results[0].page_count == 2
    assert results[0].appearance_pdf.startswith(b"%PDF")
    assert not list(renderer_directory.glob("mfirma-appearance-*.pdf"))


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_qpdf_preview_overlay_stays_inside_rotated_crop_box(
    qtbot, workdir, rotation
):
    document = _pdf(workdir / f"rotation-{rotation}.pdf", rotation=rotation)
    result = _result(document, workdir, rotation=rotation)
    page = PreviewPage()
    qtbot.addWidget(page)
    page.resize(1180, 760)
    page.show()
    page.set_documents((document,), "Certificato di firma")
    page.load_preview(result)
    qtbot.wait(50)

    assert isinstance(page.canvas.view, QPdfView)
    assert page.canvas.view.pageNavigator().currentPage() == 1
    assert page.canvas.overlay.isVisible()
    assert page.canvas._page_rect.contains(page.canvas.overlay.geometry())
    display_width, display_height = display_page_size(result.geometry)
    qt_page_size = page.canvas.document.pagePointSize(result.page_index)
    assert qt_page_size.width() == pytest.approx(display_width)
    assert qt_page_size.height() == pytest.approx(display_height)
    page_aspect = page.canvas._page_rect.width() / page.canvas._page_rect.height()
    assert page_aspect == pytest.approx(display_width / display_height, rel=0.02)
    placement = next(iter(page.placements.values()), None)
    if placement is None:
        page.apply_preset("top_left")
        placement = next(iter(page.placements.values()))
    assert result.geometry.lower_left_x <= placement.x1 < placement.x2
    assert result.geometry.lower_left_y <= placement.y1 < placement.y2


def test_preview_preset_zoom_and_custom_position_are_pdf_points(qtbot, workdir):
    document = _pdf(workdir / "preview.pdf")
    result = _result(document, workdir)
    page = PreviewPage()
    qtbot.addWidget(page)
    page.resize(1180, 760)
    page.show()
    page.set_documents((document,), "Certificato")
    page.load_preview(result)

    page.apply_preset("top_left")
    placement_before_zoom = page.placements[next(iter(page.placements))]
    page.canvas.set_zoom_factor(1.5)
    placement_after_zoom = page.placements[next(iter(page.placements))]

    assert placement_after_zoom == placement_before_zoom
    assert page.canvas.view.zoomFactor() == pytest.approx(1.5)
    page.canvas.set_display_rect(DisplayRect(60, 70, 180, 64))
    custom = page.placements[next(iter(page.placements))]
    assert custom.x1 == pytest.approx(70)
    assert custom.y1 == pytest.approx(90)


def test_overlay_can_be_dragged_and_resized_inside_page(qtbot, workdir):
    document = _pdf(workdir / "interactive.pdf")
    result = _result(document, workdir)
    page = PreviewPage()
    qtbot.addWidget(page)
    page.resize(1180, 760)
    page.show()
    page.set_documents((document,), "Certificato")
    page.load_preview(result)
    overlay = page.canvas.overlay
    initial = overlay.geometry()

    center = overlay.rect().center()
    qtbot.mousePress(overlay, Qt.MouseButton.LeftButton, pos=center)
    qtbot.mouseMove(overlay, pos=center + QPoint(-20, -15))
    qtbot.mouseRelease(
        overlay, Qt.MouseButton.LeftButton, pos=center + QPoint(-20, -15)
    )
    moved = overlay.geometry()

    assert moved.topLeft() != initial.topLeft()
    assert page.canvas._page_rect.contains(moved)
    bottom_right = overlay.rect().bottomRight()
    qtbot.mousePress(overlay, Qt.MouseButton.LeftButton, pos=bottom_right)
    qtbot.mouseMove(overlay, pos=bottom_right + QPoint(20, 10))
    qtbot.mouseRelease(
        overlay, Qt.MouseButton.LeftButton, pos=bottom_right + QPoint(20, 10)
    )
    assert overlay.width() >= moved.width()
    assert overlay.height() >= moved.height()
    assert page.canvas._page_rect.contains(overlay.geometry())


def test_apply_position_to_all_uses_normalized_page_coordinates(qtbot, workdir):
    first = _pdf(workdir / "first.pdf")
    second = _pdf(workdir / "second.pdf", rotation=90)
    first_result = _result(first, workdir)
    second_result = _result(second, workdir)
    page = PreviewPage()
    qtbot.addWidget(page)
    page.resize(1180, 760)
    page.show()
    page.set_documents((first, second), "Certificato")
    page.load_preview(first_result)
    page.apply_all.setChecked(True)
    page.canvas.set_display_rect(DisplayRect(40, 50, 160, 60))

    page._current_index = 1
    page.load_preview(second_result)

    first_size = display_page_size(first_result.geometry)
    second_size = display_page_size(second_result.geometry)
    rect = page.canvas.display_rect
    assert rect is not None
    assert rect.x / second_size[0] == pytest.approx(40 / first_size[0])
    assert rect.y / second_size[1] == pytest.approx(50 / first_size[1])

    plans = []
    page.continueRequested.connect(plans.append)
    page._continue()
    assert plans[0].placements == {}
    assert plans[0].shared_rect is not None


def test_appearance_loaded_by_preview_is_the_renderer_pdf(workdir):
    document = _pdf(workdir / "source.pdf")
    result = _result(document, workdir)
    appearance = workdir / "appearance-copy.pdf"
    appearance.write_bytes(result.appearance_pdf)

    text = PdfReader(appearance).pages[0].extract_text()

    assert "Giovanni Bergamaschi" in text
    assert "Verificare la firma con un lettore PDF" in text


def test_main_window_opens_preview_from_selected_documents(qtbot, workdir):
    document = _pdf(workdir / "from-dashboard.pdf")
    config = AppConfig()
    config.pkcs11.certificate_label = "Certificato di firma"
    repository = ConfigRepository(workdir / "config.json")
    repository.save(config)
    window = MFirmaQtWindow(repository, auto_scan=False)
    qtbot.addWidget(window)
    window.show()

    with qtbot.waitSignal(window.preview_controller.previewSucceeded, timeout=5000):
        window.open_preview((document,))

    assert window.stackedWidget.currentWidget() is window.preview_page
    assert window.preview_page.canvas.overlay.isVisible()
    assert window.preview_page.page_label.text() == "Pagina 2 di 2 · ultima pagina"
    qtbot.keyClick(window, Qt.Key.Key_Escape)
    assert window.stackedWidget.currentWidget() is window.queue_page
    assert window.wait_for_workers()
