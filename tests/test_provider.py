from __future__ import annotations

import pytest

from mfirma.config import Pkcs11Config, SignatureConfig
from mfirma.errors import ProviderConfigurationError
from mfirma.provider import Pkcs11SigningProvider, _decode_pkcs11_id


def test_decode_pkcs11_id():
    assert _decode_pkcs11_id("445333") == b"DS3"
    assert _decode_pkcs11_id("") is None


def test_decode_pkcs11_id_rejects_invalid_hex():
    with pytest.raises(ProviderConfigurationError, match="non valido"):
        _decode_pkcs11_id("not-hex")


def test_provider_uses_certificate_id_for_private_key(
    workdir, monkeypatch
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
            return object()

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
        certificate_label="Certificate label",
        certificate_id="445333",
    )
    provider = Pkcs11SigningProvider(config, SignatureConfig())

    with provider.open("1234"):
        pass

    assert captured["cert_label"] is None
    assert captured["token_criteria"].label == "TOKEN"
    assert captured["token_criteria"].serial == b"SERIAL"
    assert captured["cert_id"] == b"DS3"
    assert captured["key_label"] is None
    assert captured["key_id"] == b"DS3"
    assert captured["user_pin"] == "1234"
