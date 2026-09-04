from __future__ import annotations

import os
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from types import TracebackType
from typing import Any


COMPLETE_APPEARANCE_SIZE = (240.0, 92.0)
COMPACT_APPEARANCE_SIZE = (190.0, 68.0)
VERIFICATION_NOTICE = "Verificare la firma con un lettore PDF"


class SignatureAppearanceVariant(StrEnum):
    COMPLETE = "complete"
    COMPACT = "compact"


@dataclass(frozen=True, slots=True)
class SignatureAppearanceData:
    signer_name: str
    signing_time: datetime
    issuer_name: str
    profile: str = "PAdES B-B"
    digest_algorithm: str = "SHA-256"
    signature_number: int = 1
    organization: str = ""
    role: str = ""
    reason: str = ""
    location: str = ""

    def __post_init__(self) -> None:
        if not self.signer_name.strip():
            raise ValueError("Il nome del firmatario è obbligatorio")
        if not self.issuer_name.strip():
            raise ValueError("L'emittente del certificato è obbligatorio")
        if self.signing_time.tzinfo is None or self.signing_time.utcoffset() is None:
            raise ValueError("La data di firma deve includere il fuso orario")
        if self.signature_number < 1:
            raise ValueError("Il numero della firma deve essere positivo")


@dataclass(slots=True)
class TemporaryAppearance:
    path: Path
    _closed: bool = False

    def __enter__(self) -> Path:
        return self.path

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        if not self._closed:
            self.path.unlink(missing_ok=True)
            self._closed = True


def _first_text(value: object) -> str:
    if isinstance(value, (list, tuple)):
        for item in value:
            text = _first_text(item)
            if text:
                return text
        return ""
    return str(value).strip() if value is not None else ""


def _asn1_name_value(name: object, key: str) -> str:
    native = getattr(name, "native", None)
    if isinstance(native, dict):
        return _first_text(native.get(key))
    return ""


def _cryptography_name_value(name: object, oid_name: str) -> str:
    try:
        from cryptography.x509.oid import NameOID

        oid = getattr(NameOID, oid_name)
        attributes = name.get_attributes_for_oid(oid)  # type: ignore[attr-defined]
        return _first_text(attributes[0].value) if attributes else ""
    except (AttributeError, IndexError, TypeError):
        return ""


def _name_value(name: object, native_key: str, oid_name: str) -> str:
    return _asn1_name_value(name, native_key) or _cryptography_name_value(
        name, oid_name
    )


def appearance_data_from_certificate(
    certificate: object,
    *,
    signing_time: datetime,
    signature_number: int,
    reason: str = "",
    location: str = "",
    fallback_name: str = "Firmatario",
) -> SignatureAppearanceData:
    subject = getattr(certificate, "subject", None)
    issuer = getattr(certificate, "issuer", None)
    signer_name = _name_value(subject, "common_name", "COMMON_NAME")
    organization = _name_value(
        subject, "organization_name", "ORGANIZATION_NAME"
    )
    role = _name_value(
        subject, "organizational_unit_name", "ORGANIZATIONAL_UNIT_NAME"
    )
    issuer_name = _name_value(issuer, "common_name", "COMMON_NAME")

    if not signer_name:
        signer_name = _first_text(getattr(subject, "human_friendly", None))
    if not issuer_name:
        issuer_name = _first_text(getattr(issuer, "human_friendly", None))

    return SignatureAppearanceData(
        signer_name=signer_name or fallback_name,
        signing_time=signing_time,
        issuer_name=issuer_name or "Emittente non disponibile",
        signature_number=signature_number,
        organization=organization,
        role=role,
        reason=reason.strip(),
        location=location.strip(),
    )


def format_signing_time(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("La data di firma deve includere il fuso orario")
    zone_name = value.tzname() or ""
    if zone_name and not zone_name.startswith(("UTC+", "UTC-")):
        zone = zone_name
    else:
        offset = value.strftime("%z")
        zone = f"{offset[:3]}:{offset[3:]}" if offset else ""
    return f"{value:%d/%m/%Y} · {value:%H:%M:%S} {zone}".strip()


class ReportLabSignatureAppearanceRenderer:
    _font_lock = threading.Lock()
    _fonts_registered = False
    regular_font = "mFirmaVera"
    bold_font = "mFirmaVeraBold"

    def __init__(self, temporary_directory: Path | None = None):
        self.temporary_directory = temporary_directory

    @classmethod
    def _register_fonts(cls) -> None:
        if cls._fonts_registered:
            return
        with cls._font_lock:
            if cls._fonts_registered:
                return
            import reportlab
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont

            fonts = Path(reportlab.__file__).parent / "fonts"
            pdfmetrics.registerFont(TTFont(cls.regular_font, str(fonts / "Vera.ttf")))
            pdfmetrics.registerFont(TTFont(cls.bold_font, str(fonts / "VeraBd.ttf")))
            cls._fonts_registered = True

    def render_pdf(
        self,
        data: SignatureAppearanceData,
        *,
        width_points: float,
        height_points: float,
        variant: SignatureAppearanceVariant,
    ) -> TemporaryAppearance:
        if width_points <= 0 or height_points <= 0:
            raise ValueError("Le dimensioni dell'aspetto devono essere positive")
        self._register_fonts()
        directory = self.temporary_directory
        if directory is not None:
            directory.mkdir(parents=True, exist_ok=True)
        handle, filename = tempfile.mkstemp(
            prefix="mfirma-appearance-",
            suffix=".pdf",
            dir=directory,
        )
        os.close(handle)
        path = Path(filename)
        try:
            self._draw(path, data, width_points, height_points, variant)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return TemporaryAppearance(path)

    def _draw(
        self,
        path: Path,
        data: SignatureAppearanceData,
        width: float,
        height: float,
        variant: SignatureAppearanceVariant,
    ) -> None:
        from reportlab.pdfgen import canvas

        pdf = canvas.Canvas(
            str(path),
            pagesize=(width, height),
            pageCompression=1,
            invariant=1,
        )
        pdf.setTitle("Aspetto firma mFirma")
        if variant is SignatureAppearanceVariant.COMPLETE:
            self._draw_complete(pdf, data, width, height)
        elif variant is SignatureAppearanceVariant.COMPACT:
            self._draw_compact(pdf, data, width, height)
        else:
            raise ValueError(f"Variante aspetto non supportata: {variant}")
        pdf.showPage()
        pdf.save()

    @staticmethod
    def _fit_text(text: str, font: str, size: float, width: float) -> str:
        from reportlab.pdfbase.pdfmetrics import stringWidth

        clean = " ".join(text.split())
        if stringWidth(clean, font, size) <= width:
            return clean
        words = clean.split()
        while len(words) > 1:
            words.pop()
            candidate = " ".join(words)
            if stringWidth(candidate, font, size) <= width:
                return candidate
        while clean and stringWidth(clean, font, size) > width:
            clean = clean[:-1]
        return clean.rstrip()

    @classmethod
    def _draw_value(
        cls,
        pdf: Any,
        text: str,
        x: float,
        y: float,
        width: float,
        *,
        size: float = 7.5,
        bold: bool = False,
    ) -> None:
        font = cls.bold_font if bold else cls.regular_font
        pdf.setFont(font, size)
        pdf.setFillColorRGB(0.12, 0.15, 0.19)
        pdf.drawString(x, y, cls._fit_text(text, font, size, width))

    @classmethod
    def _draw_label(
        cls, pdf: Any, text: str, x: float, y: float, width: float
    ) -> None:
        pdf.setFont(cls.bold_font, 6.5)
        pdf.setFillColorRGB(0.15, 0.36, 0.68)
        pdf.drawString(x, y, cls._fit_text(text, cls.bold_font, 6.5, width))

    @classmethod
    def _draw_shell(
        cls, pdf: Any, width: float, height: float, left_width: float
    ) -> None:
        pdf.setFillColorRGB(1, 1, 1)
        pdf.setStrokeColorRGB(0.15, 0.40, 0.85)
        pdf.setLineWidth(1.1)
        pdf.roundRect(0.7, 0.7, width - 1.4, height - 1.4, 3, fill=1, stroke=1)
        pdf.setFillColorRGB(0.93, 0.97, 1.0)
        pdf.rect(1.3, 1.3, left_width - 1.3, height - 2.6, fill=1, stroke=0)

        pdf.setStrokeColorRGB(0.15, 0.40, 0.85)
        pdf.setLineWidth(1.2)
        icon_y = height - 16
        path = pdf.beginPath()
        path.moveTo(8, icon_y)
        path.curveTo(16, icon_y + 8, 16, icon_y - 7, 24, icon_y + 1)
        path.curveTo(29, icon_y + 6, 31, icon_y - 3, left_width - 7, icon_y + 3)
        pdf.drawPath(path, stroke=1, fill=0)

    @classmethod
    def _draw_complete(
        cls, pdf: Any, data: SignatureAppearanceData, width: float, height: float
    ) -> None:
        left_width = width * 0.235
        cls._draw_shell(pdf, width, height, left_width)
        left_x = 7
        pdf.setFillColorRGB(0.15, 0.36, 0.68)
        pdf.setFont(cls.bold_font, 8)
        pdf.drawString(left_x, height - 39, "FIRMA")
        pdf.drawString(left_x, height - 49, "DIGITALE")
        pdf.setFont(cls.bold_font, 6.5)
        pdf.drawString(left_x, height - 61, data.profile)
        pdf.drawString(left_x, height - 72, f"Firma n. {data.signature_number}")
        pdf.drawString(left_x, height - 83, data.digest_algorithm)

        x = left_width + 6
        body_width = width - x - 5
        cls._draw_label(pdf, "FIRMATO DIGITALMENTE DA", x, height - 10, body_width)

        name_size = 11.5
        name = cls._fit_text(data.signer_name, cls.bold_font, name_size, body_width)
        cls._draw_value(
            pdf, name, x, height - 24, body_width, size=name_size, bold=True
        )
        secondary = " · ".join(
            value for value in (data.organization, data.role) if value
        )
        if secondary:
            cls._draw_value(pdf, secondary, x, height - 34, body_width)

        first_width = body_width * 0.67
        second_x = x + first_width + 4
        second_width = body_width - first_width - 4
        cls._draw_label(pdf, "DATA E ORA", x, height - 45, first_width)
        cls._draw_value(
            pdf,
            format_signing_time(data.signing_time),
            x,
            height - 54,
            first_width,
        )
        if data.reason:
            cls._draw_label(pdf, "MOTIVO", second_x, height - 45, second_width)
            cls._draw_value(
                pdf, data.reason, second_x, height - 54, second_width
            )

        location_width = body_width * 0.32 if data.location else 0
        issuer_x = x + location_width + (4 if data.location else 0)
        issuer_width = body_width - location_width - (4 if data.location else 0)
        if data.location:
            cls._draw_label(pdf, "LUOGO", x, height - 64, location_width)
            cls._draw_value(pdf, data.location, x, height - 73, location_width)
        cls._draw_label(
            pdf, "CERTIFICATO EMESSO DA", issuer_x, height - 64, issuer_width
        )
        cls._draw_value(
            pdf, data.issuer_name, issuer_x, height - 73, issuer_width
        )
        cls._draw_value(pdf, VERIFICATION_NOTICE, x, 5, body_width, size=6.5)

    @classmethod
    def _draw_compact(
        cls, pdf: Any, data: SignatureAppearanceData, width: float, height: float
    ) -> None:
        left_width = width * 0.23
        cls._draw_shell(pdf, width, height, left_width)
        left_x = 6
        pdf.setFillColorRGB(0.15, 0.36, 0.68)
        pdf.setFont(cls.bold_font, 7)
        pdf.drawString(left_x, height - 31, "FIRMA")
        pdf.drawString(left_x, height - 40, "DIGITALE")
        pdf.setFont(cls.bold_font, 5.8)
        pdf.drawString(left_x, height - 49, data.profile)
        pdf.drawString(left_x, height - 58, f"n. {data.signature_number} · {data.digest_algorithm}")

        x = left_width + 5
        body_width = width - x - 4
        cls._draw_label(pdf, "FIRMATO DIGITALMENTE DA", x, height - 8, body_width)
        cls._draw_value(
            pdf, data.signer_name, x, height - 20, body_width, size=9.5, bold=True
        )
        secondary = " · ".join(
            value for value in (data.organization, data.role) if value
        )
        if secondary:
            cls._draw_value(pdf, secondary, x, height - 29, body_width, size=6.8)
        cls._draw_value(
            pdf,
            format_signing_time(data.signing_time),
            x,
            height - 39,
            body_width,
            size=7,
        )
        optional = " · ".join(value for value in (data.reason, data.location) if value)
        if optional:
            cls._draw_value(pdf, optional, x, height - 48, body_width, size=6.8)
        cls._draw_value(pdf, data.issuer_name, x, height - 57, body_width, size=6.8)
        cls._draw_value(pdf, VERIFICATION_NOTICE, x, 4, body_width, size=5.5)
