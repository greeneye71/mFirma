from __future__ import annotations

import math
import hashlib
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from .appearance import (
    ReportLabSignatureAppearanceRenderer,
    SignatureAppearanceVariant,
    appearance_data_from_certificate,
)
from .config import SignatureConfig
from .errors import PdfInvalidError, SignatureFailedError, SignedOutputInvalidError
from .models import NormalizedDisplayRect, PageGeometry, SignaturePlacement
from .placement import (
    calculate_placement,
    constrain_display_rect,
    display_rect_from_normalized,
    display_rect_from_placement,
    placement_from_display_rect,
)


def read_last_page_geometry(source: Path) -> tuple[PageGeometry, int, int]:
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


def verify_new_signature(path: Path, previous_count: int, *, expected_certificate_sha256: str) -> None:
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
            actual = hashlib.sha256(newest.signer_cert.dump()).hexdigest()
            if not expected_certificate_sha256 or actual != expected_certificate_sha256.lower():
                raise SignedOutputInvalidError("Il certificato nel PDF non corrisponde a quello selezionato")
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
    *,
    appearance_renderer: ReportLabSignatureAppearanceRenderer | None = None,
    signing_time: datetime | None = None,
    placement: SignaturePlacement | None = None,
    normalized_rect: NormalizedDisplayRect | None = None,
    phase_callback: Callable[[str], None] | None = None,
    expected_certificate_sha256: str | None = None,
) -> None:
    """Aggiunge una firma PAdES B-B visibile all'ultima pagina."""
    from pyhanko import stamp
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields, signers

    expected_certificate_sha256 = (
        hashlib.sha256(signer.signing_cert.dump()).hexdigest()
        if expected_certificate_sha256 is None else expected_certificate_sha256
    )

    geometry, page_index, _ = read_last_page_geometry(source)
    if placement is not None and normalized_rect is not None:
        raise ValueError("Indicare una sola modalità di posizionamento")
    if placement is not None:
        if placement.page_index != page_index:
            raise ValueError("La posizione non appartiene all'ultima pagina")
        display_rect = display_rect_from_placement(geometry, placement)
        constrained = constrain_display_rect(geometry, display_rect)
        if any(
            not math.isclose(actual, expected, abs_tol=1e-6)
            for actual, expected in zip(
                (
                    constrained.x,
                    constrained.y,
                    constrained.width,
                    constrained.height,
                ),
                (
                    display_rect.x,
                    display_rect.y,
                    display_rect.width,
                    display_rect.height,
                ),
                strict=True,
            )
        ):
            raise ValueError("La posizione della firma è fuori dalla pagina")
    elif normalized_rect is not None:
        placement = placement_from_display_rect(
            geometry,
            page_index=page_index,
            rect=display_rect_from_normalized(geometry, normalized_rect),
        )
    else:
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
    signature_time = signing_time or datetime.now().astimezone()
    appearance_data = appearance_data_from_certificate(
        getattr(signer, "signing_cert", None),
        signing_time=signature_time,
        signature_number=old_signature_count + 1,
        reason=settings.reason,
        location=settings.location,
        fallback_name="Firmatario",
    )
    renderer = appearance_renderer or ReportLabSignatureAppearanceRenderer()
    variant = SignatureAppearanceVariant(settings.appearance_variant)

    try:
        with renderer.render_pdf(
            appearance_data,
            width_points=settings.width_points,
            height_points=settings.height_points,
            variant=variant,
        ) as appearance_path:
            style = stamp.StaticStampStyle.from_pdf_file(
                str(appearance_path), border_width=0
            )
            with (
                source.open("rb") as input_stream,
                temporary_output.open("wb") as output_stream,
            ):
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
                    name=appearance_data.signer_name,
                )
                pdf_signer = signers.PdfSigner(
                    metadata, signer=signer, stamp_style=style
                )
                pdf_signer.sign_pdf(writer, output=output_stream)
    except Exception as exc:
        raise SignatureFailedError(f"Firma PDF non riuscita: {exc}") from exc

    if phase_callback:
        phase_callback("verifying")
    verify_new_signature(temporary_output, old_signature_count,
                         expected_certificate_sha256=expected_certificate_sha256)
