from __future__ import annotations

import pytest
import hashlib
from types import SimpleNamespace

from mfirma.config import Pkcs11Config, SignatureConfig
from mfirma.errors import ProviderConfigurationError
from mfirma.provider import Pkcs11SigningProvider, _decode_pkcs11_id


def test_decode_pkcs11_id():
    assert _decode_pkcs11_id("445333") == b"DS3"
    assert _decode_pkcs11_id("") is None


def test_session_carries_selected_fingerprint_to_every_pdf(monkeypatch, workdir):
    from mfirma.provider import _PadesSigningSession
    captured = []
    monkeypatch.setattr("mfirma.provider.sign_pades", lambda *args, **kwargs: captured.append(kwargs))
    session = _PadesSigningSession(object(), SignatureConfig(), expected_certificate_sha256="a" * 64)
    for index in range(2):
        session.sign_pdf(workdir / f"{index}.pdf", workdir / "out.pdf")
    assert [call["expected_certificate_sha256"] for call in captured] == ["a" * 64] * 2


def test_changed_certificate_closes_session_without_signing(workdir, monkeypatch):
    module = workdir / "module.dll"
    module.touch()
    closed = []
    class Context:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return SimpleNamespace(signing_cert=SimpleNamespace(dump=lambda: b"different"))
        def __exit__(self, *args):
            closed.append(True)
    monkeypatch.setattr("pyhanko.sign.pkcs11.PKCS11SigningContext", Context)
    provider = Pkcs11SigningProvider(Pkcs11Config(module_path=str(module), certificate_id="01"), SignatureConfig())
    provider.expected_certificate_sha256 = "a" * 64
    with pytest.raises(ProviderConfigurationError, match="cambiato"):
        with provider.open("test-pin"):
            pytest.fail("La sessione non deve essere disponibile")
    assert closed == [True]


def test_decode_pkcs11_id_rejects_invalid_hex():
    with pytest.raises(ProviderConfigurationError, match="non valido"):
        _decode_pkcs11_id("not-hex")


@pytest.mark.parametrize("label", ["Certificate label", ""])
def test_provider_uses_certificate_id_for_private_key(
    workdir, monkeypatch, label
):
    module = workdir / "module.dll"
    module.touch()
    captured = {}

    class FakeSignatureConfig:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeSigningContext:
        def __init__(self, _config, user_pin):
            captured["user_pin"] = user_pin

        def __enter__(self):
            return SimpleNamespace(signing_cert=SimpleNamespace(dump=lambda: b"certificate"))

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(
        "pyhanko.config.pkcs11.PKCS11SignatureConfig", FakeSignatureConfig
    )
    monkeypatch.setattr(
        "pyhanko.sign.pkcs11.PKCS11SigningContext", FakeSigningContext
    )
    config = Pkcs11Config(
        module_path=str(module),
        token_label="TOKEN",
        token_serial="53455249414c",
        certificate_label=label,
        certificate_id="445333",
    )
    provider = Pkcs11SigningProvider(config, SignatureConfig())
    provider.expected_certificate_sha256 = hashlib.sha256(b"certificate").hexdigest()

    with provider.open("1234"):
        pass

    assert captured["cert_label"] is None
    assert captured["token_criteria"].label == "TOKEN"
    assert captured["token_criteria"].serial == b"SERIAL"
    assert captured["cert_id"] == b"DS3"
    assert captured["key_label"] is None
    assert captured["key_id"] == b"DS3"
    assert captured["user_pin"] == "1234"


@pytest.mark.parametrize("fingerprint", ["", "a" * 63, "z" * 64])
def test_provider_requires_valid_selected_fingerprint(workdir, fingerprint):
    module = workdir / "module.dll"
    module.touch()
    provider = Pkcs11SigningProvider(Pkcs11Config(module_path=str(module), certificate_id="01"), SignatureConfig())
    provider.expected_certificate_sha256 = fingerprint
    with pytest.raises(ProviderConfigurationError, match="Impronta"):
        provider.validate()
