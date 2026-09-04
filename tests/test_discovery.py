from __future__ import annotations

import struct
import subprocess
from pathlib import Path

from mfirma import discovery
from mfirma.probe import _certificate_key_usage, _public_text


def _write_pe_dll(path: Path, machine: int) -> None:
    data = bytearray(0x100)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", data, 0x84, machine)
    struct.pack_into("<H", data, 0x96, 0x2000)
    path.write_bytes(data)


def test_inspect_pe_dll_recognises_x64_and_rejects_non_pe(workdir: Path):
    x64 = workdir / "vendor-pkcs11.dll"
    x86 = workdir / "vendor32-pkcs11.dll"
    text = workdir / "not-pkcs11.dll"
    _write_pe_dll(x64, 0x8664)
    _write_pe_dll(x86, 0x014C)
    text.write_text("not a PE file", encoding="utf-8")

    assert discovery.inspect_pe_dll(x64) == "x64"
    assert discovery.inspect_pe_dll(x86) == "x86"
    assert discovery.inspect_pe_dll(text) is None


def test_find_candidate_paths_is_name_filtered_and_deduplicated(workdir: Path):
    module = workdir / "middleware-pkcs11.dll"
    unrelated = workdir / "ordinary.dll"
    _write_pe_dll(module, 0x8664)
    _write_pe_dll(unrelated, 0x8664)

    found = discovery.find_candidate_paths(
        search_roots=[workdir], extra_paths=[module]
    )

    assert [path for path, _source in found] == [module.resolve()]


def test_discovery_keeps_valid_module_without_connected_token(
    workdir: Path, monkeypatch
):
    x64 = workdir / "good-pkcs11.dll"
    x86 = workdir / "old-pkcs11.dll"
    _write_pe_dll(x64, 0x8664)
    _write_pe_dll(x86, 0x014C)
    monkeypatch.setattr(discovery, "_probe_in_subprocess", lambda _path, _timeout: [])

    result = discovery.discover_pkcs11_modules(search_roots=[workdir])

    assert [candidate.path for candidate in result.candidates] == [x64.resolve()]
    assert result.candidates[0].token_labels == ()
    assert result.paths_checked == 2
    assert result.rejected == 1


def test_discovery_collects_unique_token_and_certificate_labels(
    workdir: Path, monkeypatch
):
    module = workdir / "cryptoki.dll"
    _write_pe_dll(module, 0x8664)
    payload = [
        {
            "token_label": "Token B",
            "certificates": [
                {
                    "label": "Firma",
                    "id_hex": "445333",
                    "key_usage": {"content_commitment": True},
                },
                {"label": "Firma"},
            ],
        },
        {"token_label": "Token A", "certificates": []},
    ]
    monkeypatch.setattr(
        discovery, "_probe_in_subprocess", lambda _path, _timeout: payload
    )

    result = discovery.discover_pkcs11_modules(search_roots=[workdir])

    candidate = result.candidates[0]
    assert candidate.token_labels == ("Token A", "Token B")
    assert candidate.certificate_labels == ("Firma",)
    assert candidate.document_signing_labels == ("Firma",)
    assert candidate.certificate_ids == (("Firma", "445333"),)


def test_probe_uses_console_python_when_app_runs_with_pythonw(
    workdir: Path, monkeypatch
):
    pythonw = workdir / "pythonw.exe"
    python = workdir / "python.exe"
    pythonw.touch()
    python.touch()
    called: list[list[str]] = []

    def fake_run(command, **_kwargs):
        called.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="[]", stderr="")

    monkeypatch.setattr(discovery.sys, "executable", str(pythonw))
    monkeypatch.setattr(discovery.subprocess, "run", fake_run)

    assert discovery._probe_in_subprocess(workdir / "module.dll", 1.0) == []
    assert called[0][0] == str(python)


def test_probe_normalises_byte_fields_for_json_output():
    assert _public_text(b"Firma digitale   \0") == "Firma digitale"
    assert _public_text("Token   ") == "Token"
    assert _public_text(None) == ""
    assert _certificate_key_usage(b"not a certificate") == {}
