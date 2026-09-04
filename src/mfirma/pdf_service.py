from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from .config import SignatureConfig
from .errors import PdfInvalidError, SignedOutputInvalidError
from .models import PageGeometry
from .placement import calculate_placement


def _geometry_and_page(source: Path) -> tuple[PageGeometry, int, int]:
    try:
        from pypdf import PdfReader

        reader = PdfReader(source, strict=True)
        if reader.is_encrypted:
            raise PdfInvalidError("Il PDF è cifrato")
        page_count = len(reader.pages)
        if page_count == 0:
            raise PdfInvalidError("Il PDF non contiene pagine")
        page_index = page_count - 1
        page = reader.pages[page_index]
        box = page.cropbox
        geometry = PageGeometry(
            float(box.left),
            float(box.bottom),
            float(box.right),
            float(box.top),
            int(page.rotation or 0) % 360,
        )
        return geometry, page_index, page_count
    except PdfInvalidError:
        raise
    except Exception as exc:
        raise PdfInvalidError(f"PDF non leggibile: {exc}") from exc


def embedded_signature_count(path: Path) -> int:
    try:
        from pyhanko.pdf_utils.reader import PdfFileReader

        with path.open("rb") as stream:
            return len(PdfFileReader(stream).embedded_signatures)
    except Exception as exc:
        raise PdfInvalidError(f"Impossibile leggere le firme PDF: {exc}") from exc


def verify_new_signature(path: Path, previous_count: int) -> None:
    """Verifica incremento, integrità e firma crittografica, non la fiducia legale."""
    try:
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.sign.validation import validate_pdf_signature
        from pyhanko_certvalidator import ValidationContext

        with path.open("rb") as stream:
            reader = PdfFileReader(stream)
            signatures = reader.embedded_signatures
            if len(signatures) != previous_count + 1:
                raise SignedOutputInvalidError(
                    "L'output non contiene esattamente una nuova firma"
                )
            newest = signatures[-1]
            context = ValidationContext(
                trust_roots=[newest.signer_cert], allow_fetching=False
            )
            status = validate_pdf_signature(
                newest, signer_validation_context=context
            )
            if not status.intact or not status.valid:
                raise SignedOutputInvalidError(
                    "La nuova firma non supera il controllo crittografico"
                )
    except SignedOutputInvalidError:
        raise
    except Exception as exc:
        raise SignedOutputInvalidError(f"Verifica firma non riuscita: {exc}") from exc


def sign_pades(
    source: Path,
    temporary_output: Path,
    signer: Any,
    settings: SignatureConfig,
) -> None:
    """Aggiunge una firma PAdES B-B visibile all'ultima pagina."""
    from pyhanko import stamp
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields, signers

    geometry, page_index, _ = _geometry_and_page(source)
    placement = calculate_placement(
        geometry,
        page_index=page_index,
        preset=settings.preset,
        margin=settings.margin_points,
        width=settings.width_points,
        height=settings.height_points,
    )
    old_signature_count = embedded_signature_count(source)
    field_name = f"mFirma_{uuid.uuid4().hex[:12]}"

    try:
        with source.open("rb") as input_stream, temporary_output.open("wb") as output_stream:
            writer = IncrementalPdfFileWriter(input_stream)
            fields.append_signature_field(
                writer,
                sig_field_spec=fields.SigFieldSpec(
                    sig_field_name=field_name,
                    on_page=page_index,
                    box=(placement.x1, placement.y1, placement.x2, placement.y2),
                ),
            )
            metadata = signers.PdfSignatureMetadata(
                field_name=field_name,
                md_algorithm="sha256",
                subfilter=fields.SigSeedSubFilter.PADES,
                reason=settings.reason or None,
                location=settings.location or None,
            )
            style = stamp.TextStampStyle(
                stamp_text="Firmato digitalmente da %(signer)s\nData: %(ts)s"
            )
            pdf_signer = signers.PdfSigner(metadata, signer=signer, stamp_style=style)
            pdf_signer.sign_pdf(writer, output=output_stream)
    except Exception as exc:
        raise PdfInvalidError(f"Firma PDF non riuscita: {exc}") from exc

    verify_new_signature(temporary_output, old_signature_count)

