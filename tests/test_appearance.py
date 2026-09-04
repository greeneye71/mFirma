from __future__ import annotations

import datetime

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pypdf import PdfReader

from mfirma.appearance import (
    COMPACT_APPEARANCE_SIZE,
    COMPLETE_APPEARANCE_SIZE,
    VERIFICATION_NOTICE,
    ReportLabSignatureAppearanceRenderer,
    SignatureAppearanceData,
    SignatureAppearanceVariant,
    appearance_data_from_certificate,
    format_signing_time,
)


def _data(**changes) -> SignatureAppearanceData:
    values = {
        "signer_name": "Giovànni Bergamaschi",
        "signing_time": datetime.datetime(
            2026, 9, 5, 10, 48, 32,
            tzinfo=datetime.timezone(datetime.timedelta(hours=2)),
        ),
        "issuer_name": "ArubaPEC Qualified CA",
        "organization": "Azienda Sanitaria",
        "role": "Direzione",
        "reason": "Approvazione",
        "location": "Roma",
        "signature_number": 2,
    }
    values.update(changes)
    return SignatureAppearanceData(**values)


def _has_embedded_font(reader: PdfReader) -> bool:
    fonts = reader.pages[0]["/Resources"]["/Font"].values()
    for font_reference in fonts:
        font = font_reference.get_object()
        descriptors = []
        if "/FontDescriptor" in font:
            descriptors.append(font["/FontDescriptor"])
        for descendant in font.get("/DescendantFonts", []):
            descendant = descendant.get_object()
            if "/FontDescriptor" in descendant:
                descriptors.append(descendant["/FontDescriptor"])
        if any(
            any(key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3"))
            for descriptor in descriptors
        ):
            return True
    return False


@pytest.mark.parametrize(
    ("variant", "size"),
    [
        (SignatureAppearanceVariant.COMPLETE, COMPLETE_APPEARANCE_SIZE),
        (SignatureAppearanceVariant.COMPACT, COMPACT_APPEARANCE_SIZE),
    ],
)
def test_renderer_is_vector_text_with_embedded_font_and_exact_size(
    workdir, variant, size
):
    renderer = ReportLabSignatureAppearanceRenderer(workdir)
    temporary = renderer.render_pdf(
        _data(), width_points=size[0], height_points=size[1], variant=variant
    )

    with temporary as path:
        reader = PdfReader(path)
        page = reader.pages[0]
        text = page.extract_text()
        assert float(page.mediabox.width) == size[0]
        assert float(page.mediabox.height) == size[1]
        assert "Giovànni Bergamaschi" in text
        assert "05/09/2026" in text
        assert "+02:00" in text
        assert "ArubaPEC Qualified CA" in text
        assert "PAdES B-B" in text
        assert "SHA-256" in text
        assert _has_embedded_font(reader)
        assert "/XObject" not in page["/Resources"]
        lowered = text.casefold()
        assert "firma valida" not in lowered
        assert "documento integro" not in lowered
        assert "marca temporale" not in lowered

    assert not temporary.path.exists()


def test_complete_renderer_handles_optional_and_long_fields(workdir):
    renderer = ReportLabSignatureAppearanceRenderer(workdir)
    data = _data(
        signer_name="Nome Cognome Molto Lungo Con Accenti È À Ò e caratteri Unicode",
        organization="",
        role="",
        reason="",
        location="",
    )

    with renderer.render_pdf(
        data,
        width_points=COMPLETE_APPEARANCE_SIZE[0],
        height_points=COMPLETE_APPEARANCE_SIZE[1],
        variant=SignatureAppearanceVariant.COMPLETE,
    ) as path:
        text = PdfReader(path).pages[0].extract_text()
        assert "MOTIVO" not in text
        assert "LUOGO" not in text
        assert VERIFICATION_NOTICE in text


def test_temporary_appearance_is_removed_after_error(workdir):
    renderer = ReportLabSignatureAppearanceRenderer(workdir)
    temporary = renderer.render_pdf(
        _data(),
        width_points=240,
        height_points=92,
        variant=SignatureAppearanceVariant.COMPLETE,
    )

    with pytest.raises(RuntimeError):
        with temporary:
            raise RuntimeError("errore simulato")

    assert not temporary.path.exists()


def test_data_requires_timezone_and_formats_explicit_offset():
    with pytest.raises(ValueError, match="fuso orario"):
        _data(signing_time=datetime.datetime(2026, 9, 5, 10, 48, 32))

    assert format_signing_time(_data().signing_time).endswith("+02:00")


def test_appearance_data_reads_certificate_names():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Organizzazione Prova"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Responsabile"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Firmatario Prova"),
        ]
    )
    issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "CA Prova")])
    now = datetime.datetime.now(datetime.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=30))
        .sign(key, hashes.SHA256())
    )

    data = appearance_data_from_certificate(
        certificate,
        signing_time=now,
        signature_number=3,
        reason="Revisione",
        location="Milano",
    )

    assert data.signer_name == "Firmatario Prova"
    assert data.organization == "Organizzazione Prova"
    assert data.role == "Responsabile"
    assert data.issuer_name == "CA Prova"
    assert data.signature_number == 3
    assert data.reason == "Revisione"
    assert data.location == "Milano"
