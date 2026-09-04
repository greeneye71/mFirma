from __future__ import annotations

import datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pyhanko.sign import signers
from pypdf import PdfReader, PdfWriter

from mfirma.config import SignatureConfig
from mfirma.pdf_service import embedded_signature_count, sign_pades


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

    sign_pades(source, first, signer, settings)
    sign_pades(first, second, signer, settings)

    assert embedded_signature_count(first) == 1
    assert embedded_signature_count(second) == 2
    assert len(PdfReader(second).pages) == 1

