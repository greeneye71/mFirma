from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


_DLL_NAME_MARKERS = (
    "pkcs11",
    "pkcs_11",
    "pkcs-11",
    "cryptoki",
    "etpkcs",
    "asepkcs",
    "bit4xpki",
    "bit4ipki",
)
_SKIP_DIRECTORIES = {
    "$recycle.bin",
    ".git",
    ".venv",
    "node_modules",
    "windowsapps",
}
_PE_MACHINE_NAMES = {
    0x014C: "x86",
    0x8664: "x64",
    0xAA64: "arm64",
}
_IMAGE_FILE_DLL = 0x2000


@dataclass(frozen=True, slots=True)
class ModuleCandidate:
    path: Path
    architecture: str
    source: str
    token_labels: tuple[str, ...] = ()
    certificate_labels: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    candidates: tuple[ModuleCandidate, ...]
    paths_checked: int
    rejected: int


def inspect_pe_dll(path: Path) -> str | None:
    """Return the PE architecture when *path* is a Windows DLL."""
    try:
        with path.open("rb") as stream:
            if stream.read(2) != b"MZ":
                return None
            stream.seek(0x3C)
            pe_offset_data = stream.read(4)
            if len(pe_offset_data) != 4:
                return None
            pe_offset = struct.unpack("<I", pe_offset_data)[0]
            stream.seek(pe_offset)
            header = stream.read(24)
    except (OSError, ValueError):
        return None

    if len(header) != 24 or header[:4] != b"PE\0\0":
        return None
    machine = struct.unpack("<H", header[4:6])[0]
    characteristics = struct.unpack("<H", header[22:24])[0]
    if not characteristics & _IMAGE_FILE_DLL:
        return None
    return _PE_MACHINE_NAMES.get(machine, f"0x{machine:04x}")


def _looks_like_pkcs11_name(path: Path) -> bool:
    name = path.name.casefold()
    return path.suffix.casefold() == ".dll" and any(
        marker in name for marker in _DLL_NAME_MARKERS
    )


def _walk_candidates(root: Path, max_depth: int) -> Iterator[Path]:
    stack = [(root, 0)]
    visited_directories = 0
    while stack and visited_directories < 5000:
        directory, depth = stack.pop()
        visited_directories += 1
        try:
            entries = list(os.scandir(directory))
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_file(follow_symlinks=False):
                    path = Path(entry.path)
                    if _looks_like_pkcs11_name(path):
                        yield path
                elif (
                    depth < max_depth
                    and entry.is_dir(follow_symlinks=False)
                    and entry.name.casefold() not in _SKIP_DIRECTORIES
                ):
                    stack.append((Path(entry.path), depth + 1))
            except OSError:
                continue


def _registry_search_roots() -> list[tuple[Path, str, int]]:
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []

    uninstall_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    roots: list[tuple[Path, str, int]] = []
    access_modes = {winreg.KEY_READ}
    for flag_name in ("KEY_WOW64_64KEY", "KEY_WOW64_32KEY"):
        flag = getattr(winreg, flag_name, 0)
        access_modes.add(winreg.KEY_READ | flag)

    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for access in access_modes:
            try:
                parent = winreg.OpenKey(hive, uninstall_key, 0, access)
            except OSError:
                continue
            with parent:
                index = 0
                while True:
                    try:
                        child_name = winreg.EnumKey(parent, index)
                    except OSError:
                        break
                    index += 1
                    try:
                        child = winreg.OpenKey(parent, child_name, 0, access)
                    except OSError:
                        continue
                    with child:
                        try:
                            location = winreg.QueryValueEx(child, "InstallLocation")[0]
                        except OSError:
                            continue
                        try:
                            display_name = winreg.QueryValueEx(child, "DisplayName")[0]
                        except OSError:
                            display_name = "software installato"
                    if isinstance(location, str) and location.strip():
                        expanded = os.path.expandvars(location.strip().strip('"'))
                        roots.append((Path(expanded), str(display_name), 5))
    return roots


def _default_search_roots() -> list[tuple[Path, str, int]]:
    roots = _registry_search_roots()
    for variable in ("ProgramW6432", "ProgramFiles", "LOCALAPPDATA"):
        value = os.environ.get(variable)
        if value:
            roots.append((Path(value), variable, 4 if variable != "LOCALAPPDATA" else 3))
    system_root = os.environ.get("SystemRoot")
    if system_root:
        roots.append((Path(system_root) / "System32", "Windows System32", 0))
    return roots


def find_candidate_paths(
    *,
    search_roots: Iterable[Path] | None = None,
    extra_paths: Iterable[Path] = (),
) -> list[tuple[Path, str]]:
    """Find plausible module paths without loading any DLL."""
    roots = (
        [(Path(root), "ricerca richiesta", 5) for root in search_roots]
        if search_roots is not None
        else _default_search_roots()
    )
    found: dict[str, tuple[Path, str]] = {}

    for path in extra_paths:
        candidate = Path(path).expanduser()
        if candidate.is_file():
            try:
                resolved = candidate.resolve()
            except OSError:
                resolved = candidate.absolute()
            found[str(resolved).casefold()] = (resolved, "configurazione corrente")

    seen_roots: set[str] = set()
    for root, source, depth in roots:
        try:
            resolved_root = root.expanduser().resolve()
        except OSError:
            continue
        root_key = str(resolved_root).casefold()
        if root_key in seen_roots or not resolved_root.is_dir():
            continue
        seen_roots.add(root_key)
        for candidate in _walk_candidates(resolved_root, depth):
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            found.setdefault(str(resolved).casefold(), (resolved, source))
            if len(found) >= 100:
                break
    return sorted(found.values(), key=lambda item: str(item[0]).casefold())


def _probe_in_subprocess(
    path: Path, timeout: float
) -> list[dict[str, object]] | None:
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    python_executable = Path(sys.executable)
    if python_executable.name.casefold() == "pythonw.exe":
        console_python = python_executable.with_name("python.exe")
        if console_python.is_file():
            python_executable = console_python
    try:
        completed = subprocess.run(
            [str(python_executable), "-m", "mfirma.probe", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=creation_flags,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        payload = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError):
        return None
    return payload if isinstance(payload, list) else None


def discover_pkcs11_modules(
    *,
    search_roots: Iterable[Path] | None = None,
    extra_paths: Iterable[Path] = (),
    probe_timeout: float = 6.0,
) -> DiscoveryResult:
    """Find x64 PKCS#11 modules and validate them outside the GUI process."""
    paths = find_candidate_paths(search_roots=search_roots, extra_paths=extra_paths)
    eligible: list[tuple[Path, str, str]] = []
    rejected = 0
    for path, source in paths:
        architecture = inspect_pe_dll(path)
        if architecture != "x64":
            rejected += 1
            continue
        eligible.append((path, source, architecture))

    # A broad filename match can yield unrelated DLLs. Keep resource usage
    # bounded and probe a few candidates concurrently, each in its own process.
    if len(eligible) > 32:
        rejected += len(eligible) - 32
        eligible = eligible[:32]

    def validate(
        item: tuple[Path, str, str]
    ) -> ModuleCandidate | None:
        path, source, architecture = item
        tokens = _probe_in_subprocess(path, probe_timeout)
        if tokens is None:
            return None
        # An empty list is a valid response: the middleware may be installed
        # while its smart card or USB token is currently disconnected.
        token_labels: set[str] = set()
        certificate_labels: set[str] = set()
        for token in tokens:
            if not isinstance(token, dict):
                continue
            label = token.get("token_label")
            if isinstance(label, str) and label.strip():
                token_labels.add(label.strip())
            certificates = token.get("certificates", [])
            if isinstance(certificates, list):
                for certificate in certificates:
                    if not isinstance(certificate, dict):
                        continue
                    certificate_label = certificate.get("label")
                    if isinstance(certificate_label, str) and certificate_label.strip():
                        certificate_labels.add(certificate_label.strip())
        return ModuleCandidate(
            path=path,
            architecture=architecture,
            source=source,
            token_labels=tuple(sorted(token_labels, key=str.casefold)),
            certificate_labels=tuple(sorted(certificate_labels, key=str.casefold)),
        )

    if eligible:
        with ThreadPoolExecutor(max_workers=min(4, len(eligible))) as executor:
            validated = list(executor.map(validate, eligible))
    else:
        validated = []
    candidates = [candidate for candidate in validated if candidate is not None]
    rejected += len(validated) - len(candidates)
    return DiscoveryResult(tuple(candidates), len(paths), rejected)
