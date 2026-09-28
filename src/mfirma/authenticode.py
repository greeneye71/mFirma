"""Authenticode verification of PKCS#11 DLLs without loading them."""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SIGNATURE_VALID = "valid"
SIGNATURE_UNSIGNED = "unsigned"
SIGNATURE_INVALID = "invalid"
SIGNATURE_UNKNOWN = "unknown"

_PATHS_VARIABLE = "MFIRMA_AUTHENTICODE_PATHS"
# The paths travel as Base64 UTF-8 JSON in an environment variable: nothing
# from the file system is interpolated into the script.
_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$raw = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:MFIRMA_AUTHENTICODE_PATHS))
$paths = ConvertFrom-Json -InputObject $raw
$out = @(foreach ($p in $paths) {
  try {
    $s = Get-AuthenticodeSignature -LiteralPath $p
    $subject = ''
    if ($s.SignerCertificate) { $subject = $s.SignerCertificate.Subject }
    [pscustomobject]@{ status = [string]$s.Status; subject = $subject }
  } catch {
    [pscustomobject]@{ status = 'Error'; subject = '' }
  }
})
ConvertTo-Json -InputObject $out -Compress
"""


@dataclass(frozen=True, slots=True)
class ModuleSignature:
    """Authenticode state of a DLL, as reported by Windows."""

    status: str = SIGNATURE_UNKNOWN
    publisher: str = ""
    detail: str = ""

    @property
    def trusted(self) -> bool:
        return self.status == SIGNATURE_VALID

    @property
    def summary(self) -> str:
        if self.status == SIGNATURE_VALID:
            return f"Firmata: {self.publisher}" if self.publisher else "Firmata"
        if self.status == SIGNATURE_UNSIGNED:
            return "Non firmata"
        if self.status == SIGNATURE_INVALID:
            return "Firma NON valida"
        return "Firma non verificata"


def _publisher(subject: str) -> str:
    for attribute in ("CN", "O"):
        match = re.search(rf"(?:^|,\s*){attribute}=(\"[^\"]*\"|[^,]*)", subject)
        if match:
            return match.group(1).strip().strip('"')
    return subject.strip()


def _signature_from_status(status: str, subject: str) -> ModuleSignature:
    if status == "Valid":
        return ModuleSignature(SIGNATURE_VALID, _publisher(subject), status)
    if status == "NotSigned":
        return ModuleSignature(SIGNATURE_UNSIGNED, "", status)
    if status in {"HashMismatch", "NotTrusted", "Incompatible"}:
        return ModuleSignature(SIGNATURE_INVALID, _publisher(subject), status)
    return ModuleSignature(SIGNATURE_UNKNOWN, _publisher(subject), status)


def _powershell_executable() -> Path | None:
    system_root = os.environ.get("SystemRoot")
    if not system_root:
        return None
    executable = (
        Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    )
    return executable if executable.is_file() else None


def verify_authenticode(
    paths: Iterable[Path], *, timeout: float = 20.0
) -> dict[Path, ModuleSignature]:
    """Return the Authenticode state of each path; never raises.

    Get-AuthenticodeSignature also recognises catalog-signed files. Any
    failure yields ``SIGNATURE_UNKNOWN`` rather than a trusted result.
    """
    items = list(dict.fromkeys(Path(path) for path in paths))
    unknown = {path: ModuleSignature() for path in items}
    if not items or os.name != "nt":
        return unknown
    executable = _powershell_executable()
    if executable is None:
        return unknown
    encoded = base64.b64encode(
        json.dumps([str(path) for path in items]).encode("utf-8")
    ).decode("ascii")
    environment = dict(os.environ)
    environment[_PATHS_VARIABLE] = encoded
    try:
        completed = subprocess.run(
            [
                str(executable), "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-EncodedCommand",
                base64.b64encode(_SCRIPT.encode("utf-16-le")).decode("ascii"),
            ],
            capture_output=True,
            timeout=timeout,
            env=environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
        payload = json.loads(completed.stdout.decode("utf-8-sig", errors="replace"))
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return unknown
    if not isinstance(payload, list) or len(payload) != len(items):
        return unknown
    result: dict[Path, ModuleSignature] = {}
    for path, entry in zip(items, payload):
        if not isinstance(entry, dict):
            result[path] = ModuleSignature()
            continue
        status = entry.get("status")
        subject = entry.get("subject")
        result[path] = _signature_from_status(
            status if isinstance(status, str) else "",
            subject if isinstance(subject, str) else "",
        )
    return result
