from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, PushButton, SubtitleLabel, TitleLabel

from ...models import BatchPhase, BatchProgress, JobStatus


class ProgressPage(QWidget):
    cancelRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("progressPage")
        self._completed_paths: set[str] = set()
        self._counts = {status: 0 for status in JobStatus}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(16)
        layout.addWidget(TitleLabel("Firma in corso", self))
        self.summary_label = SubtitleLabel("Preparazione…", self)
        self.summary_label.setAccessibleName("Avanzamento firma")
        layout.addWidget(self.summary_label)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setObjectName("batchProgress")
        self.progress_bar.setAccessibleName("Documenti completati")
        self.progress_bar.setRange(0, 1)
        layout.addWidget(self.progress_bar)

        current = QFrame(self)
        current.setFrameShape(QFrame.Shape.StyledPanel)
        current_layout = QVBoxLayout(current)
        current_layout.setContentsMargins(18, 16, 18, 16)
        current_layout.addWidget(BodyLabel("Documento corrente", current))
        self.file_label = SubtitleLabel("—", current)
        self.file_label.setAccessibleName("Documento corrente")
        self.person_label = BodyLabel("", current)
        self.phase_label = BodyLabel("Fase: preparazione", current)
        self.phase_label.setAccessibleName("Fase corrente")
        current_layout.addWidget(self.file_label)
        current_layout.addWidget(self.person_label)
        current_layout.addWidget(self.phase_label)
        layout.addWidget(current)

        counts = QFrame(self)
        counts.setFrameShape(QFrame.Shape.StyledPanel)
        count_layout = QGridLayout(counts)
        self.succeeded_label = SubtitleLabel("0", counts)
        self.failed_label = SubtitleLabel("0", counts)
        self.skipped_label = SubtitleLabel("0", counts)
        self.cancelled_label = SubtitleLabel("0", counts)
        for column, (title, value) in enumerate(
            (
                ("Riusciti", self.succeeded_label),
                ("Errori", self.failed_label),
                ("Saltati", self.skipped_label),
                ("Annullati", self.cancelled_label),
            )
        ):
            count_layout.addWidget(BodyLabel(title, counts), 0, column)
            count_layout.addWidget(value, 1, column)
        layout.addWidget(counts)
        layout.addStretch(1)
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.cancel_button = PushButton("Annulla dopo il file corrente", self)
        self.cancel_button.setAccessibleName("Annulla dopo il file corrente")
        actions.addWidget(self.cancel_button)
        layout.addLayout(actions)
        self.cancel_button.clicked.connect(self.cancelRequested)

    def start(self, total: int) -> None:
        self._completed_paths.clear()
        self._counts = {status: 0 for status in JobStatus}
        self.progress_bar.setRange(0, max(1, total))
        self.progress_bar.setValue(0)
        self.summary_label.setText(f"0 di {total} documenti completati")
        self.progress_bar.setAccessibleDescription(
            f"0 di {total} documenti completati"
        )
        self.file_label.setText("Preparazione del batch")
        self.person_label.setText("")
        self.phase_label.setText("Fase: preparazione")
        self.cancel_button.setEnabled(True)
        self.cancel_button.setText("Annulla dopo il file corrente")
        self._update_counts()

    def update_progress(self, event: BatchProgress) -> None:
        self.file_label.setText(event.job.document.source.name)
        self.person_label.setText(event.job.document.person or "")
        self.phase_label.setText(f"Fase: {event.phase.value}")
        if event.phase is BatchPhase.COMPLETED:
            key = str(event.job.document.source).casefold()
            if key not in self._completed_paths:
                self._completed_paths.add(key)
                self._counts[event.job.status] += 1
            self.progress_bar.setValue(event.completed)
        self.summary_label.setText(
            f"{event.completed} di {event.total} documenti completati"
        )
        self.progress_bar.setAccessibleDescription(self.summary_label.text())
        self._update_counts()

    def mark_cancel_requested(self, requested: bool) -> None:
        if requested:
            self.cancel_button.setEnabled(False)
            self.cancel_button.setText("Annullamento richiesto")
            self.phase_label.setText(
                "Annullamento richiesto: il file corrente verrà completato"
            )

    def _update_counts(self) -> None:
        self.succeeded_label.setText(str(self._counts[JobStatus.SUCCEEDED]))
        self.failed_label.setText(str(self._counts[JobStatus.FAILED]))
        self.skipped_label.setText(str(self._counts[JobStatus.SKIPPED]))
        self.cancelled_label.setText(str(self._counts[JobStatus.CANCELLED]))
