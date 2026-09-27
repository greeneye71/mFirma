from __future__ import annotations

import hashlib
import json
import struct
import subprocess
from pathlib import Path

import pytest

from mfirma import authenticode, discovery
from mfirma.authenticode import (
    SIGNATURE_INVALID,
    SIGNATURE_UNKNOWN,
    SIGNATURE_UNSIGNED,
    SIGNATURE_VALID,
    ModuleSignature,
    verify_authenticode,
)
from mfirma.config import AppConfig, Pkcs11Config, SignatureConfig
from mfirma.discovery import ModuleCandidate
from mfirma.errors import ModuleChangedError
from mfirma.provider import Pkcs11SigningProvider


def _pe_dll(path: Path) -> None:
    data = bytearray(0x100)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", data, 0x84, 0x8664)
    struct.pack_into("<H", data, 0x96, 0x2000)
    path.write_bytes(data)


def _fake_windows(monkeypatch, run) -> None:
    monkeypatch.setattr(authenticode.os, "name", "nt")
    monkeypatch.setattr(authenticode, "_powershell_executable", lambda: Path("powershell.exe"))
    monkeypatch.setattr(authenticode.subprocess, "run", run)


def test_authenticode_status_mapping_and_publisher():
    valid = authenticode._signature_from_status(
        "Valid", 'CN="Produttore, S.p.A.", O=Produttore, C=IT'
    )
    assert valid.status == SIGNATURE_VALID
    assert valid.trusted
    assert valid.summary == "Firmata: Produttore, S.p.A."
    assert authenticode._signature_from_status("NotSigned", "").summary == "Non firmata"
    for status in ("HashMismatch", "NotTrusted", "Incompatible"):
        signature = authenticode._signature_from_status(status, "CN=Altro")
        assert signature.status == SIGNATURE_INVALID
        assert signature.summary == "Firma NON valida"
        assert not signature.trusted
    assert authenticode._signature_from_status("UnknownError", "").status == SIGNATURE_UNKNOWN
    assert authenticode._publisher("O=Solo Organizzazione, C=IT") == "Solo Organizzazione"


def test_authenticode_failures_are_never_trusted(workdir: Path, monkeypatch):
    module = workdir / "vendor.dll"
    module.write_bytes(b"dll")
    monkeypatch.setattr(authenticode.os, "name", "posix")
    assert list(verify_authenticode([module]).values()) == [ModuleSignature()]

    def respond(stdout: bytes):
        return lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, stdout=stdout, stderr=b"")

    for stdout in (b"not json", b"[]", b'["Valid"]'):
        _fake_windows(monkeypatch, respond(stdout))
        assert verify_authenticode([module])[module].status == SIGNATURE_UNKNOWN

    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    _fake_windows(monkeypatch, timeout)
    assert not verify_authenticode([module])[module].trusted


def test_authenticode_passes_paths_outside_the_script(workdir: Path, monkeypatch):
    module = workdir / "vendor'; exit.dll"
    module.write_bytes(b"dll")
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        payload = [{"status": "Valid", "subject": "CN=Produttore"}]
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload).encode(), stderr=b"")

    _fake_windows(monkeypatch, fake_run)
    assert verify_authenticode([module])[module].summary == "Firmata: Produttore"
    assert all("vendor'" not in part for part in captured["command"])
    assert "MFIRMA_AUTHENTICODE_PATHS" in captured["env"]


def test_default_search_roots_skip_user_writable_folders(workdir: Path, monkeypatch):
    local = workdir / "Local"
    program_files = workdir / "Programmi"
    user_root = local / "Vendor"
    machine_root = program_files / "Vendor"
    for path in (user_root, machine_root):
        path.mkdir(parents=True)
    for variable in (
        "ProgramW6432", "ProgramFiles(x86)", "SystemRoot", "USERPROFILE", "APPDATA", "TEMP", "TMP",
    ):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("ProgramFiles", str(program_files))
    monkeypatch.setattr(
        discovery, "_registry_search_roots",
        lambda: [(user_root, "utente", 5), (machine_root, "macchina", 5)],
    )

    roots = [root for root, _source, _depth in discovery._default_search_roots()]

    assert user_root not in roots
    assert local not in roots
    assert machine_root in roots
    assert discovery.is_protected_location(machine_root / "vendor.dll")
    assert not discovery.is_protected_location(user_root / "vendor.dll")


@pytest.mark.parametrize("verify", [True, False])
def test_discovery_reports_fingerprint_location_and_signature(workdir: Path, monkeypatch, verify):
    module = workdir / "vendor-pkcs11.dll"
    _pe_dll(module)
    calls = []
    signed = ModuleSignature(SIGNATURE_VALID, "Produttore", "Valid")

    def fake_verify(paths, **_kwargs):
        paths = list(paths)
        calls.append(paths)
        return {path: signed for path in paths}

    monkeypatch.setattr(discovery, "_probe_in_subprocess", lambda _path, _timeout: [])
    monkeypatch.setattr(discovery, "verify_authenticode", fake_verify)

    result = discovery.discover_pkcs11_modules(search_roots=[workdir], verify_signatures=verify)

    candidate = result.candidates[0]
    assert candidate.sha256 == hashlib.sha256(module.read_bytes()).hexdigest()
    assert not candidate.protected_location
    assert candidate.needs_confirmation
    if verify:
        assert len(calls) == 1
        assert candidate.signature == signed
    else:
        assert not calls
        assert candidate.signature == ModuleSignature()


def test_only_signed_modules_in_protected_folders_skip_confirmation(workdir: Path):
    signed = ModuleSignature(SIGNATURE_VALID, "Produttore")

    def candidate(signature: ModuleSignature, protected: bool) -> ModuleCandidate:
        return ModuleCandidate(
            path=workdir / "a.dll", architecture="x64", source="test",
            signature=signature, protected_location=protected,
        )

    assert not candidate(signed, True).needs_confirmation
    assert candidate(signed, False).needs_confirmation
    assert candidate(ModuleSignature(SIGNATURE_UNSIGNED), True).needs_confirmation
    assert candidate(ModuleSignature(), True).needs_confirmation


def test_provider_refuses_a_changed_module(workdir: Path):
    module = workdir / "vendor.dll"
    module.write_bytes(b"originale")
    config = Pkcs11Config(
        module_path=str(module), certificate_id="01",
        module_sha256=hashlib.sha256(b"originale").hexdigest(),
    )
    provider = Pkcs11SigningProvider(config, SignatureConfig())
    provider.expected_certificate_sha256 = "a" * 64
    provider.validate()

    module.write_bytes(b"sostituita")

    with pytest.raises(ModuleChangedError) as raised:
        provider.validate()
    assert raised.value.code == "MODULE_CHANGED"


@pytest.mark.parametrize(
    "value, valid",
    [("", True), ("a" * 64, True), ("A" * 64, True), ("a" * 63, False), ("g" * 64, False)],
)
def test_config_validates_module_fingerprint(value: str, valid: bool):
    config = AppConfig()
    config.pkcs11.module_sha256 = value
    if valid:
        config.validate()
    else:
        with pytest.raises(ValueError, match="SHA-256"):
            config.validate()
