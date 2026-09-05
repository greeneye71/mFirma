from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from ...appearance import (
    ReportLabSignatureAppearanceRenderer,
    SignatureAppearanceData,
    SignatureAppearanceVariant,
)
from ...config import SignatureConfig
from ...models import DocumentCandidate, PageGeometry
from ...pdf_service import embedded_signature_count, read_last_page_geometry


@dataclass(frozen=True, slots=True)
class PreviewIdentity:
    certificate_label: str = ""
    subject: str = ""
    issuer: str = ""


@dataclass(frozen=True, slots=True)
class PreviewResult:
    document: DocumentCandidate
    geometry: PageGeometry
    page_index: int
    page_count: int
    appearance_pdf: bytes
    appearance_data: SignatureAppearanceData
    signature: SignatureConfig


def _distinguished_name_value(value: str, oid_name: str) -> str:
    if not value:
        return ""
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID

        name = x509.Name.from_rfc4514_string(value)
        attributes = name.get_attributes_for_oid(getattr(NameOID, oid_name))
        return str(attributes[0].value).strip() if attributes else ""
    except (AttributeError, IndexError, TypeError, ValueError):
        return ""


def preview_appearance_data(
    identity: PreviewIdentity,
    *,
    signing_time: datetime,
    signature_number: int,
    reason: str,
    location: str,
) -> SignatureAppearanceData:
    signer_name = (
        _distinguished_name_value(identity.subject, "COMMON_NAME")
        or identity.certificate_label.strip()
        or "Firmatario da certificato"
    )
    issuer_name = (
        _distinguished_name_value(identity.issuer, "COMMON_NAME")
        or identity.issuer.strip()
        or "Emittente letta al momento della firma"
    )
    return SignatureAppearanceData(
        signer_name=signer_name,
        signing_time=signing_time,
        issuer_name=issuer_name,
        organization=_distinguished_name_value(identity.subject, "ORGANIZATION_NAME"),
        role=_distinguished_name_value(
            identity.subject, "ORGANIZATIONAL_UNIT_NAME"
        ),
        reason=reason,
        location=location,
        signature_number=signature_number,
    )


class _PreviewSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(object, str)


class _PreviewWorker(QRunnable):
    def __init__(
        self,
        document: DocumentCandidate,
        signature: SignatureConfig,
        identity: PreviewIdentity,
        renderer: ReportLabSignatureAppearanceRenderer,
    ):
        super().__init__()
        self.signals = _PreviewSignals()
        self._document = document
        self._signature = signature
        self._identity = identity
        self._renderer = renderer

    @Slot()
    def run(self) -> None:
        try:
            geometry, page_index, page_count = read_last_page_geometry(
                self._document.source
            )
            signature_number = embedded_signature_count(self._document.source) + 1
            data = preview_appearance_data(
                self._identity,
                signing_time=datetime.now().astimezone(),
                signature_number=signature_number,
                reason=self._signature.reason,
                location=self._signature.location,
            )
            with self._renderer.render_pdf(
                data,
                width_points=self._signature.width_points,
                height_points=self._signature.height_points,
                variant=SignatureAppearanceVariant(
                    self._signature.appearance_variant
                ),
            ) as appearance_path:
                appearance_pdf = appearance_path.read_bytes()
            result = PreviewResult(
                document=self._document,
                geometry=geometry,
                page_index=page_index,
                page_count=page_count,
                appearance_pdf=appearance_pdf,
                appearance_data=data,
                signature=self._signature,
            )
        except Exception as exc:
            self.signals.failed.emit(self._document, str(exc))
            return
        self.signals.succeeded.emit(result)


class PreviewController(QObject):
    previewStarted = Signal(object)
    previewSucceeded = Signal(object)
    previewFailed = Signal(object, str)
    busyChanged = Signal(bool)

    def __init__(
        self,
        parent=None,
        *,
        thread_pool: QThreadPool | None = None,
        renderer: ReportLabSignatureAppearanceRenderer | None = None,
    ):
        super().__init__(parent)
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._renderer = renderer or ReportLabSignatureAppearanceRenderer()
        self._worker: _PreviewWorker | None = None

    @property
    def busy(self) -> bool:
        return self._worker is not None

    def prepare(
        self,
        document: DocumentCandidate,
        signature: SignatureConfig,
        identity: PreviewIdentity,
    ) -> bool:
        if self.busy:
            return False
        worker = _PreviewWorker(
            document,
            deepcopy(signature),
            identity,
            self._renderer,
        )
        worker.signals.succeeded.connect(self._succeeded)
        worker.signals.failed.connect(self._failed)
        self._worker = worker
        self.previewStarted.emit(document)
        self.busyChanged.emit(True)
        self._thread_pool.start(worker)
        return True

    @Slot(object)
    def _succeeded(self, result: PreviewResult) -> None:
        self._worker = None
        self.busyChanged.emit(False)
        self.previewSucceeded.emit(result)

    @Slot(object, str)
    def _failed(self, document: DocumentCandidate, message: str) -> None:
        self._worker = None
        self.busyChanged.emit(False)
        self.previewFailed.emit(document, message)

    def wait_for_done(self, timeout_ms: int = 3000) -> bool:
        return self._thread_pool.waitForDone(timeout_ms)
