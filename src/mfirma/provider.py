from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any, Iterator, Protocol

from .config import Pkcs11Config, SignatureConfig
from .errors import ProviderConfigurationError
from .models import NormalizedDisplayRect, SignaturePlacement
from .pdf_service import sign_pades


def _decode_pkcs11_id(value: str) -> bytes | None:
    if not value:
        return None
    try:
        decoded = bytes.fromhex(value)
    except ValueError as exc:
        raise ProviderConfigurationError("ID PKCS#11 del certificato non valido") from exc
    if not decoded:
        raise ProviderConfigurationError("ID PKCS#11 del certificato vuoto")
    return decoded


def _decode_token_serial(value: str) -> bytes | None:
    if not value:
        return None
    try:
        decoded = bytes.fromhex(value)
    except ValueError as exc:
        raise ProviderConfigurationError(
            "Seriale PKCS#11 del token non valido"
        ) from exc
    if not decoded:
        raise ProviderConfigurationError("Seriale PKCS#11 del token vuoto")
    return decoded


class SigningSession(Protocol):
    def sign_pdf(
        self,
        source: Path,
        temporary_output: Path,
        *,
        placement: SignaturePlacement | None = None,
        normalized_rect: NormalizedDisplayRect | None = None,
        phase_callback: Callable[[str], None] | None = None,
    ) -> None: ...


class SigningProvider(Protocol):
    def open(self, pin: str | None) -> AbstractContextManager[SigningSession]: ...


@dataclass(slots=True)
class _PadesSigningSession:
    signer: Any
    settings: SignatureConfig
    signing_time: datetime | None = None

    def sign_pdf(
        self,
        source: Path,
        temporary_output: Path,
        *,
        placement: SignaturePlacement | None = None,
        normalized_rect: NormalizedDisplayRect | None = None,
        phase_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.signing_time = datetime.now().astimezone()
        sign_pades(
            source,
            temporary_output,
            self.signer,
            self.settings,
            signing_time=self.signing_time,
            placement=placement,
            normalized_rect=normalized_rect,
            phase_callback=phase_callback,
        )


class Pkcs11SigningProvider:
    def __init__(self, config: Pkcs11Config, signature: SignatureConfig):
        self.config = config
        self.signature = signature
        self.expected_certificate_sha256 = ""

    def validate(self) -> None:
        if not self.config.module_path:
            raise ProviderConfigurationError("Indicare la DLL PKCS#11")
        module = Path(self.config.module_path).expanduser()
        if not module.is_file():
            raise ProviderConfigurationError(f"DLL PKCS#11 non trovata: {module}")
        if not self.config.certificate_label and not self.config.certificate_id:
            raise ProviderConfigurationError("Selezionare il certificato di firma")

    @contextmanager
    def open(self, pin: str | None) -> Iterator[SigningSession]:
        self.validate()
        try:
            from pyhanko.config.pkcs11 import PKCS11SignatureConfig, TokenCriteria
            from pyhanko.sign.pkcs11 import PKCS11SigningContext

            token_serial = _decode_token_serial(self.config.token_serial)
            criteria = None
            if self.config.token_label or token_serial:
                criteria = TokenCriteria(
                    label=self.config.token_label or None,
                    serial=token_serial,
                )
            certificate_id = _decode_pkcs11_id(self.config.certificate_id)
            key_label = self.config.key_label or None
            config = PKCS11SignatureConfig(
                module_path=str(Path(self.config.module_path).resolve()),
                token_criteria=criteria,
                cert_label=None if certificate_id else self.config.certificate_label,
                cert_id=certificate_id,
                key_label=key_label,
                key_id=certificate_id if certificate_id and not key_label else None,
            )
            signing_context = PKCS11SigningContext(config, user_pin=pin)
            signer = signing_context.__enter__()
        except Exception as exc:
            raise ProviderConfigurationError(
                f"Impossibile aprire il dispositivo PKCS#11: {exc}"
            ) from exc
        try:
            if self.expected_certificate_sha256:
                actual = hashlib.sha256(signer.signing_cert.dump()).hexdigest()
                if actual != self.expected_certificate_sha256:
                    raise ProviderConfigurationError("Il certificato sulla tessera è cambiato dopo la selezione")
            yield _PadesSigningSession(signer, self.signature)
        finally:
            signing_context.__exit__(None, None, None)
