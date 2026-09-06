from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt

from ...models import JobStatus, SignJob


_STATUS_LABELS = {
    JobStatus.SUCCEEDED: "Riuscito",
    JobStatus.FAILED: "Errore",
    JobStatus.SKIPPED: "Saltato",
    JobStatus.CANCELLED: "Annullato",
    JobStatus.PENDING: "In attesa",
    JobStatus.CHECKING: "Controllo",
    JobStatus.SIGNING: "Firma",
}

_ERROR_MESSAGES = {
    "SOURCE_DELETE_FAILED": "File firmato salvato; non è stato possibile eliminare l'originale.",
    "FILE_CHANGED": "Il documento è cambiato dopo la selezione.",
    "OUTPUT_EXISTS": "Esiste già un file con il nome di destinazione.",
    "PDF_INVALID": "Il PDF non può essere firmato.",
    "SIGNED_OUTPUT_INVALID": "Il controllo della nuova firma non è riuscito.",
    "MODULE_LOAD_FAILED": "Il dispositivo di firma non è disponibile.",
    "SIGNATURE_FAILED": "La firma non è riuscita.",
    "OUTPUT_WRITE_FAILED": "Non è stato possibile scrivere il file di output.",
}


def status_label(status: JobStatus) -> str:
    return _STATUS_LABELS[status]


def status_user_message(status: JobStatus, error_code: str | None) -> str:
    if error_code == "REGISTER_WRITE_FAILED":
        return "Errore nel registro delle firme. Controllare il registro locale."
    if status is JobStatus.SUCCEEDED:
        return "Firma completata"
    if status is JobStatus.CANCELLED:
        return "Non iniziato per annullamento richiesto"
    return _ERROR_MESSAGES.get(error_code or "", "Operazione non riuscita.")


def user_message(job: SignJob) -> str:
    if job.register_error:
        return ("PDF firmato salvato, ma registrazione non riuscita."
                if job.signature_saved else "Registro firme non disponibile; operazione non completata.")
    return status_user_message(job.status, job.error_code)


class BatchResultModel(QAbstractTableModel):
    HEADERS = ("Documento", "Persona", "Stato", "Output", "Messaggio")
    JOB_ROLE = int(Qt.ItemDataRole.UserRole) + 1

    def __init__(self, jobs: tuple[SignJob, ...] = (), parent=None):
        super().__init__(parent)
        self._jobs = jobs

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._jobs)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(self.HEADERS)
        ):
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._jobs):
            return None
        job = self._jobs[index.row()]
        if role == self.JOB_ROLE:
            return job
        if role == Qt.ItemDataRole.ToolTipRole:
            return str(job.document.source)
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        values = (
            job.document.source.name,
            job.document.person or "—",
            status_label(job.status),
            str(job.destination) if job.status is JobStatus.SUCCEEDED or job.error_code == "SOURCE_DELETE_FAILED" else "—",
            user_message(job),
        )
        return values[index.column()]

    def set_jobs(self, jobs: list[SignJob] | tuple[SignJob, ...]) -> None:
        self.beginResetModel()
        self._jobs = tuple(jobs)
        self.endResetModel()

    @property
    def jobs(self) -> tuple[SignJob, ...]:
        return self._jobs


class ProblemsFilterModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._problems_only = False

    def set_problems_only(self, enabled: bool) -> None:
        self._problems_only = enabled
        self.beginFilterChange()
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        if not self._problems_only:
            return True
        model = self.sourceModel()
        if not isinstance(model, BatchResultModel):
            return False
        job = model.data(model.index(source_row, 0, source_parent), model.JOB_ROLE)
        return job is not None and (job.status is not JobStatus.SUCCEEDED or job.register_error)
