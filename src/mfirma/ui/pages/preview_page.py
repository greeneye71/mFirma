from __future__ import annotations

from PySide6.QtCore import (
    QBuffer,
    QIODevice,
    QMargins,
    QPoint,
    QPointF,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CheckBox,
    ComboBox,
    PrimaryPushButton,
    PushButton,
    RadioButton,
    SubtitleLabel,
    TitleLabel,
)

from ...models import (
    DisplayRect,
    DocumentCandidate,
    NormalizedDisplayRect,
    PageGeometry,
    SignaturePlacement,
    SignaturePositionPlan,
)
from ...placement import (
    calculate_display_rect,
    constrain_display_rect,
    display_rect_from_normalized,
    display_page_size,
    display_rect_from_placement,
    normalized_from_display_rect,
    placement_from_display_rect,
)
from ..state import normalized_path
from ..workers import PreviewResult


class _SignatureOverlay(QWidget):
    geometryEdited = Signal()
    HANDLE_SIZE = 9

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image = QImage()
        self._drag_mode = ""
        self._press_position = QPoint()
        self._start_geometry = QRect()
        self._page_rect = QRect()
        self.setMouseTracking(True)
        self.setMinimumSize(24, 16)

    def set_image(self, image: QImage) -> None:
        self._image = image
        self.update()

    def set_page_rect(self, rect: QRect) -> None:
        self._page_rect = rect

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if not self._image.isNull():
            painter.drawImage(self.rect(), self._image)
        painter.setPen(QPen(QColor("#2667D8"), 2, Qt.PenStyle.DashLine))
        painter.drawRect(self.rect().adjusted(1, 1, -2, -2))
        painter.setBrush(QColor("white"))
        painter.setPen(QPen(QColor("#2667D8"), 2))
        for handle in self._handles().values():
            painter.drawRect(handle)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._drag_mode = self._hit_test(event.position().toPoint()) or "move"
        self._press_position = self.mapToParent(event.position().toPoint())
        self._start_geometry = self.geometry()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        local = event.position().toPoint()
        if not self._drag_mode:
            mode = self._hit_test(local)
            if mode in {"top_left", "bottom_right"}:
                cursor = Qt.CursorShape.SizeFDiagCursor
            elif mode in {"top_right", "bottom_left"}:
                cursor = Qt.CursorShape.SizeBDiagCursor
            else:
                cursor = Qt.CursorShape.SizeAllCursor
            self.setCursor(cursor)
            return
        current = self.mapToParent(local)
        delta = current - self._press_position
        rect = QRect(self._start_geometry)
        if self._drag_mode == "move":
            rect.moveTopLeft(rect.topLeft() + delta)
        else:
            if "left" in self._drag_mode:
                rect.setLeft(rect.left() + delta.x())
            if "right" in self._drag_mode:
                rect.setRight(rect.right() + delta.x())
            if "top" in self._drag_mode:
                rect.setTop(rect.top() + delta.y())
            if "bottom" in self._drag_mode:
                rect.setBottom(rect.bottom() + delta.y())
        self.setGeometry(self._bounded(rect))
        self.geometryEdited.emit()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._drag_mode:
            self._drag_mode = ""
            self.geometryEdited.emit()
            event.accept()

    def _bounded(self, rect: QRect) -> QRect:
        minimum_width = min(80, self._page_rect.width())
        minimum_height = min(30, self._page_rect.height())
        if rect.width() < minimum_width:
            if "left" in self._drag_mode:
                rect.setLeft(rect.right() - minimum_width + 1)
            else:
                rect.setRight(rect.left() + minimum_width - 1)
        if rect.height() < minimum_height:
            if "top" in self._drag_mode:
                rect.setTop(rect.bottom() - minimum_height + 1)
            else:
                rect.setBottom(rect.top() + minimum_height - 1)
        if self._drag_mode == "move":
            rect.moveLeft(
                min(
                    max(rect.left(), self._page_rect.left()),
                    self._page_rect.right() - rect.width() + 1,
                )
            )
            rect.moveTop(
                min(
                    max(rect.top(), self._page_rect.top()),
                    self._page_rect.bottom() - rect.height() + 1,
                )
            )
        else:
            rect = rect.intersected(self._page_rect)
        return rect

    def _handles(self) -> dict[str, QRect]:
        return {
            "top_left": QRect(0, 0, self.HANDLE_SIZE, self.HANDLE_SIZE),
            "top_right": QRect(
                self.width() - self.HANDLE_SIZE,
                0,
                self.HANDLE_SIZE,
                self.HANDLE_SIZE,
            ),
            "bottom_left": QRect(
                0,
                self.height() - self.HANDLE_SIZE,
                self.HANDLE_SIZE,
                self.HANDLE_SIZE,
            ),
            "bottom_right": QRect(
                self.width() - self.HANDLE_SIZE,
                self.height() - self.HANDLE_SIZE,
                self.HANDLE_SIZE,
                self.HANDLE_SIZE,
            ),
        }

    def _hit_test(self, point: QPoint) -> str:
        for name, rect in self._handles().items():
            if rect.adjusted(-3, -3, 3, 3).contains(point):
                return name
        return ""


class PdfPreviewCanvas(QWidget):
    placementChanged = Signal(object)
    displayRectChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.document = QPdfDocument(self)
        self.view = QPdfView(self)
        self.view.setDocument(self.document)
        self.view.setPageMode(QPdfView.PageMode.SinglePage)
        self.view.setDocumentMargins(QMargins(12, 12, 12, 12))
        self.view.setZoomMode(QPdfView.ZoomMode.FitInView)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.overlay = _SignatureOverlay(self)
        self.overlay.hide()
        self._geometry: PageGeometry | None = None
        self._page_index = 0
        self._display_rect: DisplayRect | None = None
        self._page_rect = QRect()
        self._fit_to_page = True
        self.overlay.geometryEdited.connect(self._overlay_edited)
        self.view.zoomFactorChanged.connect(self._update_overlay_geometry)
        self.view.horizontalScrollBar().valueChanged.connect(
            self._update_overlay_geometry
        )
        self.view.verticalScrollBar().valueChanged.connect(
            self._update_overlay_geometry
        )

    @property
    def display_rect(self) -> DisplayRect | None:
        return self._display_rect

    def load_preview(self, result: PreviewResult, rect: DisplayRect) -> None:
        self.document.close()
        error = self.document.load(str(result.document.source))
        if error not in (None, QPdfDocument.Error.None_):
            raise ValueError("Il documento non può essere mostrato nell’anteprima")
        self._geometry = result.geometry
        self._page_index = result.page_index
        self._display_rect = constrain_display_rect(result.geometry, rect)
        self.overlay.set_image(self._render_appearance(result))
        self.view.pageNavigator().jump(result.page_index, QPointF(0, 0), 0)
        self.fit_page()
        self.overlay.show()
        self.overlay.raise_()
        self._update_overlay_geometry()
        self._emit_placement()

    def set_display_rect(self, rect: DisplayRect) -> None:
        if self._geometry is None:
            return
        self._display_rect = constrain_display_rect(self._geometry, rect)
        self._update_overlay_geometry()
        self._emit_placement()

    def fit_page(self) -> None:
        self._fit_to_page = True
        if self._geometry is not None:
            width, height = display_page_size(self._geometry)
            margins = self.view.documentMargins()
            viewport = self.view.viewport()
            available_width = max(
                1, viewport.width() - margins.left() - margins.right()
            )
            available_height = max(
                1, viewport.height() - margins.top() - margins.bottom()
            )
            factor = min(available_width / width, available_height / height)
            self.view.setZoomMode(QPdfView.ZoomMode.Custom)
            self.view.setZoomFactor(factor)
        self._update_overlay_geometry()

    def set_zoom_factor(self, factor: float) -> None:
        self._fit_to_page = False
        self.view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.view.setZoomFactor(factor)
        self._update_overlay_geometry()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._fit_to_page:
            self.fit_page()
        else:
            self._update_overlay_geometry()

    @staticmethod
    def _render_appearance(result: PreviewResult) -> QImage:
        buffer = QBuffer()
        buffer.setData(result.appearance_pdf)
        if not buffer.open(QIODevice.OpenModeFlag.ReadOnly):
            raise ValueError("Aspetto firma non leggibile")
        document = QPdfDocument()
        try:
            error = document.load(buffer)
            if error not in (None, QPdfDocument.Error.None_):
                raise ValueError("Aspetto firma non leggibile")
            size = QSize(
                max(1, round(result.signature.width_points * 4)),
                max(1, round(result.signature.height_points * 4)),
            )
            return document.render(0, size)
        finally:
            document.close()
            buffer.close()

    def _update_overlay_geometry(self, *_args) -> None:
        if self._geometry is None or self._display_rect is None:
            return
        display_width, display_height = display_page_size(self._geometry)
        zoom = self.view.zoomFactor()
        viewport = self.view.viewport()
        margins = self.view.documentMargins()
        page_width = max(1, round(display_width * zoom))
        page_height = max(1, round(display_height * zoom))
        available_width = max(
            1, viewport.width() - margins.left() - margins.right()
        )
        available_height = max(
            1, viewport.height() - margins.top() - margins.bottom()
        )
        origin = viewport.mapTo(self, QPoint(0, 0))
        x = origin.x() + margins.left() + max(
            0, (available_width - page_width) // 2
        )
        y = origin.y() + margins.top() + max(
            0, (available_height - page_height) // 2
        )
        x -= self.view.horizontalScrollBar().value()
        y -= self.view.verticalScrollBar().value()
        self._page_rect = QRect(x, y, page_width, page_height)
        rect = self._display_rect
        overlay = QRect(
            round(x + rect.x * zoom),
            round(y + (display_height - rect.y - rect.height) * zoom),
            max(1, round(rect.width * zoom)),
            max(1, round(rect.height * zoom)),
        )
        self.overlay.set_page_rect(self._page_rect)
        self.overlay.setGeometry(overlay)
        self.overlay.raise_()

    def _overlay_edited(self) -> None:
        if self._geometry is None or self._page_rect.width() <= 0:
            return
        display_width, display_height = display_page_size(self._geometry)
        scale = self._page_rect.width() / display_width
        overlay = self.overlay.geometry()
        self._display_rect = constrain_display_rect(
            self._geometry,
            DisplayRect(
                (overlay.left() - self._page_rect.left()) / scale,
                display_height
                - (overlay.top() - self._page_rect.top()) / scale
                - overlay.height() / scale,
                overlay.width() / scale,
                overlay.height() / scale,
            ),
        )
        self._emit_placement()

    def _emit_placement(self) -> None:
        if self._geometry is None or self._display_rect is None:
            return
        placement = placement_from_display_rect(
            self._geometry,
            page_index=self._page_index,
            rect=self._display_rect,
        )
        self.placementChanged.emit(placement)
        self.displayRectChanged.emit(self._display_rect)


class PreviewPage(QWidget):
    backRequested = Signal()
    documentRequested = Signal(int)
    continueRequested = Signal(object)

    PRESETS = (
        ("Alto sinistra", "top_left"),
        ("Alto destra", "top_right"),
        ("Basso sinistra", "bottom_left"),
        ("Basso destra", "bottom_right"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("previewPage")
        self._documents: tuple[DocumentCandidate, ...] = ()
        self._current_index = 0
        self._current_result: PreviewResult | None = None
        self._placements: dict[str, SignaturePlacement] = {}
        self._shared_normalized_rect: NormalizedDisplayRect | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 20)
        layout.setSpacing(12)
        header = QHBoxLayout()
        self.back_button = PushButton("Torna ai documenti", self)
        header.addWidget(self.back_button)
        title_box = QVBoxLayout()
        title_box.addWidget(TitleLabel("Controlla e firma", self))
        self.document_label = BodyLabel("", self)
        title_box.addWidget(self.document_label)
        header.addLayout(title_box, 1)
        self.previous_button = PushButton("Documento precedente", self)
        self.next_button = PushButton("Documento successivo", self)
        header.addWidget(self.previous_button)
        header.addWidget(self.next_button)
        layout.addLayout(header)

        controls = QHBoxLayout()
        self.page_label = BodyLabel("Pagina —", self)
        controls.addWidget(self.page_label)
        controls.addStretch(1)
        controls.addWidget(BodyLabel("Zoom", self))
        self.zoom = ComboBox(self)
        for text, value in (
            ("Adatta", 0.0),
            ("75%", 0.75),
            ("100%", 1.0),
            ("125%", 1.25),
            ("150%", 1.5),
            ("200%", 2.0),
        ):
            self.zoom.addItem(text, userData=value)
        controls.addWidget(self.zoom)
        self.reset_button = PushButton("Ripristina preset", self)
        controls.addWidget(self.reset_button)
        layout.addLayout(controls)

        content = QHBoxLayout()
        self.canvas = PdfPreviewCanvas(self)
        self.canvas.setObjectName("pdfPreview")
        self.canvas.setAccessibleName("Anteprima ultima pagina PDF")
        self.canvas.setAccessibleDescription(
            "La posizione può essere scelta anche con i quattro preset nella barra laterale"
        )
        content.addWidget(self.canvas, 1)
        side = QFrame(self)
        side.setFrameShape(QFrame.Shape.StyledPanel)
        side.setFixedWidth(285)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(16, 16, 16, 16)
        side_layout.addWidget(SubtitleLabel("Riepilogo", side))
        self.count_label = BodyLabel("0 documenti", side)
        self.certificate_label = BodyLabel("Certificato non configurato", side)
        self.certificate_label.setWordWrap(True)
        side_layout.addWidget(self.count_label)
        side_layout.addWidget(self.certificate_label)
        side_layout.addWidget(BodyLabel("Formato: PAdES B-B", side))
        side_layout.addWidget(
            BodyLabel("Output: nuovo file, nessuna sovrascrittura", side)
        )
        side_layout.addSpacing(12)
        side_layout.addWidget(SubtitleLabel("Posizione", side))
        self.preset_group = QButtonGroup(self)
        self.preset_buttons: dict[str, RadioButton] = {}
        for text, preset in self.PRESETS:
            button = RadioButton(text, side)
            self.preset_group.addButton(button)
            self.preset_buttons[preset] = button
            side_layout.addWidget(button)
            button.clicked.connect(
                lambda _checked=False, value=preset: self.apply_preset(value)
            )
        self.apply_all = CheckBox("Applica questa posizione a tutti", side)
        side_layout.addWidget(self.apply_all)
        side_layout.addStretch(1)
        self.preview_notice = BodyLabel(
            "La data e l’ora mostrate sono dimostrative e saranno rigenerate durante la firma.",
            side,
        )
        self.preview_notice.setWordWrap(True)
        side_layout.addWidget(self.preview_notice)
        self.status_label = BodyLabel("", side)
        self.status_label.setWordWrap(True)
        side_layout.addWidget(self.status_label)
        self.continue_button = PrimaryPushButton("Continua e firma", side)
        side_layout.addWidget(self.continue_button)
        content.addWidget(side)
        layout.addLayout(content, 1)

        self.back_button.clicked.connect(self.backRequested)
        self.previous_button.clicked.connect(lambda: self._request_document(-1))
        self.next_button.clicked.connect(lambda: self._request_document(1))
        self.zoom.currentIndexChanged.connect(self._zoom_changed)
        self.reset_button.clicked.connect(self._reset_preset)
        self.continue_button.clicked.connect(self._continue)
        self.canvas.placementChanged.connect(self._placement_changed)
        self.canvas.displayRectChanged.connect(self._display_rect_changed)
        self.apply_all.toggled.connect(self._apply_all_changed)

    def set_documents(
        self, documents: tuple[DocumentCandidate, ...], certificate: str
    ) -> None:
        self._documents = documents
        self._current_index = 0
        self._current_result = None
        self._placements.clear()
        self._shared_normalized_rect = None
        self.count_label.setText(f"{len(documents)} documenti")
        self.certificate_label.setText(
            certificate or "Certificato non configurato"
        )
        self._update_navigation()

    def load_preview(self, result: PreviewResult) -> None:
        self._current_result = result
        self.document_label.setText(result.document.source.name)
        self.page_label.setText(
            f"Pagina {result.page_index + 1} di {result.page_count} · ultima pagina"
        )
        key = normalized_path(result.document.source)
        if self.apply_all.isChecked() and self._shared_normalized_rect:
            rect = constrain_display_rect(
                result.geometry,
                display_rect_from_normalized(
                    result.geometry, self._shared_normalized_rect
                ),
            )
        elif key in self._placements:
            rect = display_rect_from_placement(
                result.geometry, self._placements[key]
            )
        else:
            rect = calculate_display_rect(
                result.geometry,
                preset=result.signature.preset,
                margin=result.signature.margin_points,
                width=result.signature.width_points,
                height=result.signature.height_points,
            )
        self.canvas.load_preview(result, rect)
        self.preset_buttons[result.signature.preset].setChecked(True)
        self.status_label.setText("Anteprima pronta")
        self.set_busy(False)

    def set_busy(self, busy: bool) -> None:
        self.previous_button.setEnabled(not busy and self._current_index > 0)
        self.next_button.setEnabled(
            not busy and self._current_index + 1 < len(self._documents)
        )
        self.continue_button.setEnabled(not busy and bool(self._documents))
        self.reset_button.setEnabled(not busy)
        if busy:
            self.status_label.setText("Preparazione dell’anteprima…")

    def set_error(self, message: str) -> None:
        self.status_label.setText(message)
        self.set_busy(False)

    def apply_preset(self, preset: str) -> None:
        result = self._current_result
        if result is None:
            return
        rect = calculate_display_rect(
            result.geometry,
            preset=preset,
            margin=result.signature.margin_points,
            width=result.signature.width_points,
            height=result.signature.height_points,
        )
        self.canvas.set_display_rect(rect)
        self.preset_buttons[preset].setChecked(True)

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def documents(self) -> tuple[DocumentCandidate, ...]:
        return self._documents

    @property
    def placements(self) -> dict[str, SignaturePlacement]:
        return dict(self._placements)

    def _request_document(self, delta: int) -> None:
        new_index = self._current_index + delta
        if 0 <= new_index < len(self._documents):
            self._current_index = new_index
            self._current_result = None
            self._update_navigation()
            self.set_busy(True)
            self.documentRequested.emit(new_index)

    def _update_navigation(self) -> None:
        self.previous_button.setEnabled(self._current_index > 0)
        self.next_button.setEnabled(
            self._current_index + 1 < len(self._documents)
        )

    def _zoom_changed(self, _index: int) -> None:
        factor = float(self.zoom.currentData())
        if factor:
            self.canvas.set_zoom_factor(factor)
        else:
            self.canvas.fit_page()

    def _reset_preset(self) -> None:
        result = self._current_result
        if result is not None:
            self.apply_preset(result.signature.preset)

    def _placement_changed(self, placement: SignaturePlacement) -> None:
        if self._current_result is not None:
            key = normalized_path(self._current_result.document.source)
            self._placements[key] = placement

    def _display_rect_changed(self, rect: DisplayRect) -> None:
        if not self.apply_all.isChecked() or self._current_result is None:
            return
        self._shared_normalized_rect = normalized_from_display_rect(
            self._current_result.geometry,
            rect,
        )

    def _apply_all_changed(self, checked: bool) -> None:
        if not checked:
            self._shared_normalized_rect = None
        elif self._current_result is not None and self.canvas.display_rect is not None:
            self._display_rect_changed(self.canvas.display_rect)

    def _continue(self) -> None:
        self.continueRequested.emit(
            SignaturePositionPlan(
                placements={}
                if self._shared_normalized_rect is not None
                else self.placements,
                shared_rect=self._shared_normalized_rect,
            )
        )
