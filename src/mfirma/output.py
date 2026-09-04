from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .errors import OutputExistsError


def destination_for(source: Path, suffix: str = "_firmato") -> Path:
    source = source.resolve()
    if source.suffix.casefold() != ".pdf":
        raise ValueError("Il sorgente non è un PDF")
    if not suffix or any(char in suffix for char in '<>:"/\\|?*'):
        raise ValueError("Suffisso non valido")
    return source.with_name(f"{source.stem}{suffix}{source.suffix}")


def create_temporary_output(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise OutputExistsError(f"Esiste già: {destination.name}")
    handle, name = tempfile.mkstemp(
        prefix=f".{destination.stem}-", suffix=".tmp", dir=destination.parent
    )
    os.close(handle)
    return Path(name)


def publish_temporary(temporary: Path, destination: Path) -> None:
    if destination.exists():
        raise OutputExistsError(f"Esiste già: {destination.name}")
    # Su Windows os.rename non sostituisce una destinazione apparsa nel frattempo.
    os.rename(temporary, destination)

