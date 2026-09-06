from __future__ import annotations

import datetime
import hashlib
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pyhanko.sign import signers
from pypdf import PdfReader, PdfWriter

from mfirma.appearance import ReportLabSignatureAppearanceRenderer
from mfirma.config import SignatureConfig
from mfirma.models import SignaturePlacement
from mfirma.pdf_service import embedded_signature_count, sign_pades, verify_new_signature
from mfirma.errors import SignedOutputInvalidError


def _resources_have_embedded_font(resources) -> bool:
    for font_reference in resources.get("/Font", {}).values():
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
    for xobject_reference in resources.get("/XObject", {}).values():
        xobject = xobject_reference.get_object()
        nested_resources = xobject.get("/Resources")
        if nested_resources and _resources_have_embedded_font(nested_resources):
            return True
    return False


class RecordingAppearanceRenderer(ReportLabSignatureAppearanceRenderer):
    def __init__(self, temporary_directory: Path):
        super().__init__(temporary_directory)
        self.rendered_data = []

    def render_pdf(self, data, **kwargs):
        self.rendered_data.append(data)
        return super().render_pdf(data, **kwargs)


def make_signer(workdir: Path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Firmatario di test")])
    now = datetime.datetime.now(datetime.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=30))
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    key_path = workdir / "key.pem"
    cert_path = workdir / "cert.pem"
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return signers.SimpleSigner.load(str(key_path), str(cert_path))


def test_final_pdf_must_contain_selected_certificate(workdir):
    source = workdir / "source.pdf"
    output = workdir / "signed.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.write(source)
    signer = make_signer(workdir)
    fingerprint = hashlib.sha256(signer.signing_cert.dump()).hexdigest()
    sign_pades(source, output, signer, SignatureConfig(), expected_certificate_sha256=fingerprint)
    verify_new_signature(output, 0, expected_certificate_sha256=fingerprint)
    for wrong in ("0" * 64, ""):
        with pytest.raises(SignedOutputInvalidError, match="certificato"):
            verify_new_signature(output, 0, expected_certificate_sha256=wrong)
    with pytest.raises(SignedOutputInvalidError, match="certificato"):
        sign_pades(source, output, signer, SignatureConfig(), expected_certificate_sha256="0" * 64)


def test_pades_supports_batch_style_sequential_cosigning(workdir: Path):
    source = workdir / "source.pdf"
    first = workdir / "first.pdf"
    second = workdir / "second.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    with source.open("wb") as stream:
        writer.write(stream)
    signer = make_signer(workdir)
    settings = SignatureConfig(preset="bottom_right")
    renderer = RecordingAppearanceRenderer(workdir)

    sign_pades(source, first, signer, settings, appearance_renderer=renderer)
    sign_pades(first, second, signer, settings, appearance_renderer=renderer)

    assert embedded_signature_count(first) == 1
    assert embedded_signature_count(second) == 2
    assert len(PdfReader(second).pages) == 1
    assert [data.signature_number for data in renderer.rendered_data] == [1, 2]


def test_pades_uses_appearance_metadata_and_cleans_temporary_files(workdir: Path):
    source = workdir / "metadata-source.pdf"
    output = workdir / "metadata-signed.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    with source.open("wb") as stream:
        writer.write(stream)
    signer = make_signer(workdir)
    renderer = RecordingAppearanceRenderer(workdir)
    settings = SignatureConfig(
        preset="top_left",
        reason="Approvazione del documento",
        location="Roma",
    )

    sign_pades(
        source,
        output,
        signer,
        settings,
        appearance_renderer=renderer,
        signing_time=datetime.datetime(
            2026, 9, 5, 10, 48, 32, tzinfo=datetime.timezone.utc
        ),
    )

    from pyhanko.pdf_utils.reader import PdfFileReader

    with output.open("rb") as stream:
        signature = PdfFileReader(stream).embedded_signatures[0].sig_object
        assert str(signature["/Reason"]) == "Approvazione del documento"
        assert str(signature["/Location"]) == "Roma"
        assert str(signature["/Name"]) == "Firmatario di test"
    output_reader = PdfReader(output)
    signature_widget = output_reader.pages[0]["/Annots"][-1].get_object()
    normal_appearance = signature_widget["/AP"]["/N"].get_object()
    assert _resources_have_embedded_font(normal_appearance["/Resources"])
    assert renderer.rendered_data[0].reason == "Approvazione del documento"
    assert renderer.rendered_data[0].location == "Roma"
    assert not list(workdir.glob("mfirma-appearance-*.pdf"))


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_pades_appearance_stays_valid_on_rotated_pages(workdir: Path, rotation: int):
    source = workdir / f"source-{rotation}.pdf"
    output = workdir / f"signed-{rotation}.pdf"
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    page.rotate(rotation)
    with source.open("wb") as stream:
        writer.write(stream)

    sign_pades(
        source,
        output,
        make_signer(workdir),
        SignatureConfig(preset="bottom_right"),
        appearance_renderer=ReportLabSignatureAppearanceRenderer(workdir),
    )

    assert embedded_signature_count(output) == 1
    assert len(PdfReader(output).pages) == 1
    assert not list(workdir.glob("mfirma-appearance-*.pdf"))


def test_pades_uses_explicit_preview_placement_and_reports_verification(workdir: Path):
    source = workdir / "explicit-source.pdf"
    output = workdir / "explicit-signed.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    with source.open("wb") as stream:
        writer.write(stream)
    placement = SignaturePlacement(0, 44.5, 61.25, 264.5, 145.25)
    phases = []

    sign_pades(
        source,
        output,
        make_signer(workdir),
        SignatureConfig(),
        placement=placement,
        phase_callback=phases.append,
        appearance_renderer=ReportLabSignatureAppearanceRenderer(workdir),
    )

    widget = PdfReader(output).pages[0]["/Annots"][-1].get_object()
    assert [float(value) for value in widget["/Rect"]] == pytest.approx(
        [44.5, 61.25, 264.5, 145.25]
    )
    assert phases == ["verifying"]
    assert embedded_signature_count(output) == 1
