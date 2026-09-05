from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .models import DocumentCandidate


@dataclass(frozen=True, slots=True)
class ScanResult:
    documents: tuple[DocumentCandidate, ...]
    counts_by_person: dict[str, int]
    errors: tuple[str, ...] = ()

    @property
    def total(self) -> int:
        return len(self.documents)


@dataclass(frozen=True, slots=True)
class ImportResult:
    documents: tuple[DocumentCandidate, ...]
    errors: tuple[str, ...] = ()


def _is_hidden(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


def scan_root(
    root: Path,
    *,
    recursive: bool = True,
    stability_seconds: int = 5,
    output_suffix: str = "_firmato",
    now_ns: int | None = None,
) -> ScanResult:
    root = root.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(root)

    now_ns = time.time_ns() if now_ns is None else now_ns
    minimum_age_ns = stability_seconds * 1_000_000_000
    documents: list[DocumentCandidate] = []
    errors: list[str] = []

    people = sorted(
        (entry for entry in root.iterdir() if entry.is_dir() and not entry.name.startswith(".")),
        key=lambda entry: entry.name.casefold(),
    )
    for person_dir in people:
        iterator = person_dir.rglob("*") if recursive else person_dir.glob("*")
        try:
            paths = sorted(iterator, key=lambda path: str(path).casefold())
        except OSError as exc:
            errors.append(f"{person_dir}: {exc}")
            continue
        for path in paths:
            try:
                relative = path.relative_to(root)
                if _is_hidden(relative) or not path.is_file():
                    continue
                if path.suffix.casefold() != ".pdf":
                    continue
                if path.stem.casefold().endswith(output_suffix.casefold()):
                    continue
                stat = path.stat()
                if now_ns - stat.st_mtime_ns < minimum_age_ns:
                    continue
                with path.open("rb") as stream:
                    stream.read(1)
                documents.append(
                    DocumentCandidate(
                        source=path.resolve(),
                        person=person_dir.name,
                        size=stat.st_size,
                        modified_ns=stat.st_mtime_ns,
                    )
                )
            except OSError as exc:
                errors.append(f"{path}: {exc}")

    documents.sort(
        key=lambda item: (
            (item.person or "").casefold(),
            str(item.source).casefold(),
        )
    )
    counts = Counter(item.person or "Senza persona" for item in documents)
    return ScanResult(tuple(documents), dict(sorted(counts.items())), tuple(errors))


def candidates_from_paths(paths: list[Path]) -> tuple[DocumentCandidate, ...]:
    unique: dict[str, DocumentCandidate] = {}
    for path in paths:
        candidate = DocumentCandidate.from_path(path)
        if candidate.source.suffix.casefold() != ".pdf":
            continue
        unique[str(candidate.source).casefold()] = candidate
    return tuple(sorted(unique.values(), key=lambda item: str(item.source).casefold()))


def import_candidates(paths: tuple[Path, ...]) -> ImportResult:
    """Load explicitly selected PDFs without failing the entire selection."""
    unique: dict[str, DocumentCandidate] = {}
    errors: list[str] = []
    for path in paths:
        try:
            candidate = DocumentCandidate.from_path(path)
            if candidate.source.suffix.casefold() != ".pdf":
                errors.append(f"{path.name}: il file non è un PDF")
                continue
            unique[str(candidate.source).casefold()] = candidate
        except (OSError, ValueError) as exc:
            errors.append(f"{path.name}: {exc}")
    documents = tuple(
        sorted(unique.values(), key=lambda item: str(item.source).casefold())
    )
    return ImportResult(documents, tuple(errors))
