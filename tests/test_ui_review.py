"""Regressioni dei flussi UI e della corrispondenza fra pagina PDF e overlay."""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFontDatabase, QGuiApplication
from PySide6.QtPdf import QPdfDocument
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from mfirma.appearance import ReportLabSignatureAppearanceRenderer, SignatureAppearanceData, SignatureAppearanceVariant
from mfirma.config import AppConfig, ConfigRepository, SignatureConfig
from mfirma.discovery import CertificateCandidate, TokenCandidate
from mfirma.models import DisplayRect, DocumentCandidate
from mfirma.pdf_service import read_last_page_geometry
from mfirma.scanner import ScanResult
from mfirma.ui.dialogs import CertificateSelectionDialog
from mfirma.ui.main_window import MFirmaQtWindow
from mfirma.ui.pages.preview_page import PdfPreviewCanvas, PreviewPage
from mfirma.ui.workers import PreviewResult, ScanController


@pytest.fixture(autouse=True)
def offscreen_fonts(qapp):
    # Il backend offscreen non carica automaticamente i caratteri di Windows.
    for filename in ("segoeui.ttf", "segoeuib.ttf", "segoeuil.ttf", "seguisb.ttf"):
        path = Path("C:/Windows/Fonts") / filename
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))


def save_qa(image, name):
    if os.environ.get("MFIRMA_VISUAL_QA") == "1":
        folder = Path(__file__).parent / "_runtime" / "visual-review"
        folder.mkdir(parents=True, exist_ok=True)
        assert image.save(str(folder / name))


def a4_preview(workdir):
    path = workdir / "documento-A4.pdf"
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.rect(0, 0, *A4, fill=1, stroke=0)
    pdf.setFillColorRGB(0.15, 0.15, 0.15)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(45, A4[1] - 62, "Documento A4 di prova")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(45, A4[1] - 85, "Controllo della firma e dei quattro bordi della pagina")
    pdf.showPage()
    pdf.save()
    document = DocumentCandidate.from_path(path, "Mario Rossi")
    geometry, page_index, page_count = read_last_page_geometry(path)
    signature = SignatureConfig()
    data = SignatureAppearanceData(
        signer_name="Mario Rossi", issuer_name="Autorità di certificazione",
        signing_time=datetime(2026, 9, 6, 15, 30, tzinfo=timezone(timedelta(hours=2))),
    )
    with ReportLabSignatureAppearanceRenderer(workdir).render_pdf(
        data, width_points=signature.width_points, height_points=signature.height_points,
        variant=SignatureAppearanceVariant.COMPLETE,
    ) as appearance:
        appearance_pdf = appearance.read_bytes()
    result = PreviewResult(document, geometry, page_index, page_count, appearance_pdf, data, signature)
    save_qa(PdfPreviewCanvas._render_appearance(result), "signature.png")
    return result


def test_a4_page_bounds_match_rendered_white_paper_and_all_edges(qtbot, workdir):
    result = a4_preview(workdir)
    page = PreviewPage()
    qtbot.addWidget(page)
    page.resize(1180, 760)
    page.show()
    page.set_documents((result.document,), "Da scegliere alla firma")
    page.load_preview(result)
    qtbot.wait(150)
    viewer = page.canvas
    viewer.overlay.hide()
    viewport = viewer.view.viewport()
    # Misura il foglio effettivamente disegnato, non soltanto la geometria calcolata.
    def white_paper_ready():
        image = viewport.grab().toImage()
        return image.pixelColor(viewer._page_rect.center()) == QColor("white")

    qtbot.waitUntil(white_paper_ready, timeout=3000)
    screenshot = viewport.grab().toImage()
    middle = viewer._page_rect.center()
    white_x = [x for x in range(screenshot.width()) if screenshot.pixelColor(x, middle.y()) == QColor("white")]
    white_y = [y for y in range(screenshot.height()) if screenshot.pixelColor(middle.x(), y) == QColor("white")]
    assert min(white_x) == pytest.approx(viewer._page_rect.left(), abs=1)
    assert max(white_x) == pytest.approx(viewer._page_rect.right(), abs=1)
    assert min(white_y) == pytest.approx(viewer._page_rect.top(), abs=1)
    assert max(white_y) == pytest.approx(viewer._page_rect.bottom(), abs=1)
    assert viewer.view.verticalScrollBar().maximum() == 0
    assert viewer.view.horizontalScrollBar().maximum() == 0
    viewer.overlay.show()
    width, height = result.geometry.width, result.geometry.height
    for x in (0, width - result.signature.width_points):
        for y in (0, height - result.signature.height_points):
            viewer.set_display_rect(DisplayRect(x, y, result.signature.width_points, result.signature.height_points))
            overlay = viewer.overlay.geometry()
            expected_x = viewer._page_rect.left() if x == 0 else viewer._page_rect.right() - overlay.width() + 1
            expected_y = viewer._page_rect.bottom() - overlay.height() + 1 if y == 0 else viewer._page_rect.top()
            assert overlay.x() == pytest.approx(expected_x, abs=1)
            assert overlay.y() == pytest.approx(expected_y, abs=1)
            viewer._overlay_edited()
            assert viewer.display_rect.x == pytest.approx(x, abs=2)
            assert viewer.display_rect.y == pytest.approx(y, abs=2)
    page.apply_preset("bottom_right")
    save_qa(page.grab(), "preview-a4.png")


def test_layout_modes_selection_and_bottom_settings(qtbot, workdir):
    result = a4_preview(workdir)
    repository = ConfigRepository(workdir / "config.json")
    config = AppConfig()
    config.monitor.root = str(workdir)
    repository.save(config)
    window = MFirmaQtWindow(repository, auto_scan=False)
    window.setMicaEffectEnabled(False)
    qtbot.addWidget(window)
    window.show()
    page = window.queue_page
    page.set_documents(ScanResult((result.document,), {"Mario Rossi": 1}))
    page.table.selectRow(0)
    page.select_all_visible()
    qtbot.wait(70)
    assert not hasattr(page, "device_status")
    assert not hasattr(page, "certificate_status")
    assert page.select_visible_button.text() == "Seleziona tutti"
    assert page.prepare_button.text() == "Prepara la firma · 1 documento"
    assert window._settings_navigation.mapTo(window, QPoint()).y() > window._history_navigation.mapTo(window, QPoint()).y() + 100
    # La selezione resta piena anche senza focus sulla tabella.
    page.search.setFocus()
    cell = page.table.visualRect(page.proxy.index(0, 1))
    image = page.table.viewport().grab().toImage()
    assert image.pixelColor(cell.right() - 5, cell.center().y()).name() == "#245cb5"
    save_qa(window.grab(), "dashboard-folder.png")
    window.settings_page.mode.setCurrentIndex(window.settings_page.mode.findData("manual"))
    window.save_settings()
    assert window.config.mode == "manual"
    assert not page.people_panel.isVisible()
    assert not page.refresh_button.isVisible()
    assert page.model.rowCount() == 0
    assert page.add_button.isVisible()
    page.merge_documents((result.document,), select=True)
    qtbot.wait(20)
    save_qa(window.grab(), "dashboard-manual.png")
    assert window.wait_for_workers()


def test_manual_mode_never_starts_scan_even_with_saved_directory(qtbot, workdir):
    calls = []
    controller = ScanController(scanner=lambda *args, **kwargs: calls.append(args))
    config = AppConfig(mode="manual")
    config.monitor.root = str(workdir)
    repository = ConfigRepository(workdir / "config.json")
    repository.save(config)
    window = MFirmaQtWindow(repository, scan_controller=controller)
    qtbot.addWidget(window)
    window.refresh_documents()
    qtbot.wait(30)
    assert not calls
    assert window.wait_for_workers()


def test_certificate_holder_is_cn_with_full_details_available(qtbot):
    certificate = CertificateCandidate(
        label="Firma", id_hex="01", subject=r"CN=Rossi\, Mario,O=Azienda,C=IT",
        issuer="CN=Autorità di certificazione", content_commitment=True,
    )
    dialog = CertificateSelectionDialog(TokenCandidate(slot_id=1, certificates=(certificate,)))
    qtbot.addWidget(dialog)
    dialog.show()
    index = dialog.model.index(0, 2)
    assert dialog.model.data(index) == "Rossi, Mario"
    assert "O=Azienda" in dialog.model.data(index, Qt.ItemDataRole.ToolTipRole)
    save_qa(dialog.grab(), "certificate.png")


@pytest.mark.parametrize("corner", ["bottom_left", "top_right"])
def test_a4_preview_position_is_used_in_real_signed_pdf(qtbot, workdir, corner):
    from pypdf import PdfReader
    from mfirma.pdf_service import sign_pades
    from test_pdf_service import make_signer

    result = a4_preview(workdir)
    page = PreviewPage()
    qtbot.addWidget(page)
    page.set_documents((result.document,), "Test")
    page.load_preview(result)
    page.apply_preset(corner)
    placement = next(iter(page.placements.values()))
    output = workdir / "firmato.pdf"
    sign_pades(result.document.source, output, make_signer(workdir), result.signature, placement=placement)
    signed = PdfReader(output)
    field = signed.pages[0]["/Annots"][0].get_object()
    assert list(field["/Rect"]) == pytest.approx([placement.x1, placement.y1, placement.x2, placement.y2])
    assert placement.x2 - placement.x1 == pytest.approx(212.6)
    assert placement.y2 - placement.y1 == pytest.approx(92)
    if corner == "bottom_left":
        assert placement.x1 == pytest.approx(8.5)
        assert placement.y1 == pytest.approx(8.5)
    else:
        assert result.geometry.width - placement.x2 == pytest.approx(8.5)
        assert result.geometry.height - placement.y2 == pytest.approx(8.5)
