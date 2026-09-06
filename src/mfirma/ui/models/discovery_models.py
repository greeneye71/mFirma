from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from ...discovery import CertificateCandidate, ModuleCandidate, TokenCandidate


class ModuleTableModel(QAbstractTableModel):
    HEADERS = ("DLL x64", "Token rilevati", "Certificati pubblici", "Origine")
    CANDIDATE_ROLE = int(Qt.ItemDataRole.UserRole) + 1

    def __init__(self, candidates: tuple[ModuleCandidate, ...], parent=None):
        super().__init__(parent)
        self._candidates = candidates

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._candidates)

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
        if not index.isValid() or not 0 <= index.row() < len(self._candidates):
            return None
        candidate = self._candidates[index.row()]
        if role == self.CANDIDATE_ROLE:
            return candidate
        if role == Qt.ItemDataRole.ToolTipRole:
            return str(candidate.path)
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if index.column() == 0:
            return str(candidate.path)
        if index.column() == 1:
            if candidate.tokens:
                return ", ".join(
                    token.label or f"slot {token.slot_id}"
                    for token in candidate.tokens
                )
            return ", ".join(candidate.token_labels) or "Nessuno collegato"
        if index.column() == 2:
            return ", ".join(candidate.certificate_labels) or "—"
        if index.column() == 3:
            return candidate.source
        return None

    def candidate(self, row: int) -> ModuleCandidate | None:
        return self._candidates[row] if 0 <= row < len(self._candidates) else None


class CertificateTableModel(QAbstractTableModel):
    HEADERS = ("Etichetta", "Uso rilevato", "Intestatario", "Emittente", "Scadenza")
    CERTIFICATE_ROLE = int(Qt.ItemDataRole.UserRole) + 1

    def __init__(self, candidate: ModuleCandidate | TokenCandidate, parent=None):
        super().__init__(parent)
        certificates = candidate.certificates or tuple(
            CertificateCandidate(label=label, content_commitment=label in candidate.document_signing_labels)
            for label in candidate.certificate_labels
        )
        self._certificates = tuple(sorted(
            certificates,
            key=lambda item: (not item.content_commitment, item.label.casefold(), item.id_hex),
        ))

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._certificates)

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
        if not index.isValid() or not 0 <= index.row() < len(self._certificates):
            return None
        certificate = self._certificates[index.row()]
        if role == self.CERTIFICATE_ROLE:
            return certificate
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        values = (
            certificate.label,
            self._purpose(certificate),
            certificate.subject,
            certificate.issuer,
            certificate.not_after,
        )
        return values[index.column()]

    def certificate(self, row: int) -> CertificateCandidate | None:
        return self._certificates[row] if 0 <= row < len(self._certificates) else None

    def _purpose(self, certificate: CertificateCandidate) -> str:
        if certificate.content_commitment:
            return "Firma documenti"
        if certificate.digital_signature:
            return "Firma / autenticazione"
        return "Altro / non determinato"


class TokenTableModel(QAbstractTableModel):
    HEADERS = ("Etichetta", "Seriale", "Produttore", "Modello", "Slot")
    TOKEN_ROLE = int(Qt.ItemDataRole.UserRole) + 1

    def __init__(self, tokens: tuple[TokenCandidate, ...], parent=None):
        super().__init__(parent)
        self._tokens = tokens

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._tokens)

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
        if not index.isValid() or not 0 <= index.row() < len(self._tokens):
            return None
        token = self._tokens[index.row()]
        if role == self.TOKEN_ROLE:
            return token
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        values = (
            token.label or "(senza etichetta)",
            token.serial or token.serial_hex or "—",
            token.manufacturer or "—",
            token.model or "—",
            str(token.slot_id),
        )
        return values[index.column()]

    def token(self, row: int) -> TokenCandidate | None:
        return self._tokens[row] if 0 <= row < len(self._tokens) else None
