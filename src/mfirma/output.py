from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .errors import OutputExistsError


def destination_for(
    source: Path, suffix: str = "_firmato", *, directory: Path | None = None,
    overwrite_source: bool = False,
) -> Path:
    source = source.resolve()
    if source.suffix.casefold() != ".pdf":
        raise ValueError("Il sorgente non è un PDF")
    if not suffix or any(char in suffix for char in '<>:"/\\|?*'):
        raise ValueError("Suffisso non valido")
    if overwrite_source:
        return source
    parent = directory.resolve() if directory is not None else source.parent
    return parent / f"{source.stem}{suffix}{source.suffix}"


def create_temporary_output(destination: Path, *, overwrite: bool = False) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        raise OutputExistsError(f"Esiste già: {destination.name}")
    handle, name = tempfile.mkstemp(
        prefix=f".{destination.stem}-", suffix=".tmp", dir=destination.parent
    )
    os.close(handle)
    return Path(name)


def publish_temporary(
    temporary: Path, destination: Path, *, overwrite: bool = False,
) -> None:
    if overwrite:
        os.replace(temporary, destination)
        return
    if destination.exists():
        raise OutputExistsError(f"Esiste già: {destination.name}")
    # Su Windows os.rename non sostituisce una destinazione apparsa nel frattempo.
    os.rename(temporary, destination)
