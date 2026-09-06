from __future__ import annotations

from collections import Counter
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, CheckBox, PushButton, SubtitleLabel, TitleLabel

from ...models import JobStatus, SignJob
from ..models import BatchResultModel, ProblemsFilterModel, user_message


class ResultPage(QWidget):
    backRequested = Signal()
    openFolderRequested = Signal(object)
    openLogRequested = Signal(object)

    def __init__(self, parent=None, *, log_path: Path | None = None):
        super().__init__(parent)
        self.setObjectName("resultPage")
        self.model = BatchResultModel(parent=self)
        self.proxy = ProblemsFilterModel(self)
        self.proxy.setSourceModel(self.model)
        self._common_folder: Path | None = None
        self._log_path = log_path
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        self.title = TitleLabel("Firma completata", self)
        self.subtitle = BodyLabel("", self)
        self.log_hint = BodyLabel("", self)
        self.log_hint.setWordWrap(True)
        self.log_hint.hide()
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addWidget(self.log_hint)

        counts = QFrame(self)
        counts.setFrameShape(QFrame.Shape.StyledPanel)
        count_layout = QGridLayout(counts)
        self.count_labels = {
            JobStatus.SUCCEEDED: SubtitleLabel("0", counts),
            JobStatus.FAILED: SubtitleLabel("0", counts),
            JobStatus.SKIPPED: SubtitleLabel("0", counts),
            JobStatus.CANCELLED: SubtitleLabel("0", counts),
        }
        for column, (status, title) in enumerate(
            (
                (JobStatus.SUCCEEDED, "Riusciti"),
                (JobStatus.FAILED, "Errori"),
                (JobStatus.SKIPPED, "Saltati"),
                (JobStatus.CANCELLED, "Annullati"),
            )
        ):
            count_layout.addWidget(BodyLabel(title, counts), 0, column)
            count_layout.addWidget(self.count_labels[status], 1, column)
        layout.addWidget(counts)

        self.table = QTableView(self)
        self.table.setObjectName("batchResultTable")
        self.table.setAccessibleName("Risultati della firma")
        self.table.setModel(self.proxy)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for column, width in enumerate((230, 140, 100, 320, 300)):
            self.table.setColumnWidth(column, width)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.back_button = PushButton("Torna ai documenti", self)
        self.open_folder_button = PushButton("Apri cartella", self)
        self.copy_button = PushButton("Copia riepilogo", self)
        self.open_log_button = PushButton("Apri log errori", self)
        self.open_log_button.setAccessibleName("Apri il log tecnico degli errori")
        self.open_log_button.hide()
        self.problems_only = CheckBox("Mostra solo problemi", self)
        actions.addWidget(self.back_button)
        actions.addWidget(self.open_folder_button)
        actions.addWidget(self.copy_button)
        actions.addWidget(self.open_log_button)
        actions.addStretch(1)
        actions.addWidget(self.problems_only)
        layout.addLayout(actions)
        self.back_button.clicked.connect(self.backRequested)
        self.open_folder_button.clicked.connect(self._open_folder)
        self.copy_button.clicked.connect(self.copy_summary)
        self.open_log_button.clicked.connect(self._open_log)
        self.problems_only.toggled.connect(self.proxy.set_problems_only)

    def set_jobs(self, jobs: list[SignJob] | tuple[SignJob, ...]) -> None:
        jobs = tuple(jobs)
        self.model.set_jobs(jobs)
        counts = Counter(job.status for job in jobs)
        for status, label in self.count_labels.items():
            label.setText(str(counts[status]))
        if counts[JobStatus.CANCELLED]:
            self.title.setText("Firma annullata in modo controllato")
        elif counts[JobStatus.FAILED] or counts[JobStatus.SKIPPED]:
            self.title.setText("Firma completata con segnalazioni")
        else:
            self.title.setText("Firma completata")
        self.subtitle.setText(f"Elaborati {len(jobs)} documenti")
        folders = {
            job.destination.parent
            for job in jobs
            if job.status is JobStatus.SUCCEEDED or job.error_code == "SOURCE_DELETE_FAILED"
        }
        self._common_folder = next(iter(folders)) if len(folders) == 1 else None
        self.open_folder_button.setEnabled(self._common_folder is not None)
        has_problems = any(job.status is not JobStatus.SUCCEEDED for job in jobs)
        self.problems_only.setVisible(has_problems)
        self.problems_only.setChecked(False)
        show_log = has_problems and self._log_path is not None
        self.open_log_button.setVisible(show_log)
        self.log_hint.setVisible(show_log)
        if show_log:
            self.log_hint.setText(
                f"Dettagli tecnici registrati in: {self._log_path}"
            )

    def set_log_path(self, path: Path) -> None:
        self._log_path = path

    def summary_text(self) -> str:
        lines = [self.title.text(), self.subtitle.text()]
        lines.extend(
            f"{job.document.source.name}: {user_message(job)}"
            for job in self.model.jobs
        )
        return "\n".join(lines)

    def copy_summary(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.summary_text())

    def _open_folder(self) -> None:
        if self._common_folder is not None:
            self.openFolderRequested.emit(self._common_folder)

    def _open_log(self) -> None:
        if self._log_path is not None:
            self.openLogRequested.emit(self._log_path)
