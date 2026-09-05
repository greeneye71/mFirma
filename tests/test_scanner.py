from pathlib import Path

from mfirma.scanner import candidates_from_paths, import_candidates, scan_root


def test_scans_people_recursively_and_excludes_signed(workdir: Path):
    mario = workdir / "Mario Rossi"
    lucia = workdir / "Lucia"
    (mario / "pratica").mkdir(parents=True)
    lucia.mkdir()
    (mario / "uno.pdf").write_bytes(b"pdf")
    (mario / "pratica" / "due.PDF").write_bytes(b"pdf")
    (mario / "uno_firmato.pdf").write_bytes(b"pdf")
    (lucia / "tre.pdf").write_bytes(b"pdf")
    (lucia / "note.txt").write_text("no", encoding="utf-8")

    result = scan_root(workdir, stability_seconds=0)

    assert result.total == 3
    assert result.counts_by_person == {"Lucia": 1, "Mario Rossi": 2}
    assert [item.person for item in result.documents] == [
        "Lucia",
        "Mario Rossi",
        "Mario Rossi",
    ]


def test_manual_candidates_are_deduplicated_case_insensitively(workdir: Path):
    source = workdir / "test.pdf"
    source.write_bytes(b"pdf")
    candidates = candidates_from_paths([source, source])
    assert len(candidates) == 1


def test_import_candidates_keeps_valid_pdfs_when_one_path_fails(workdir: Path):
    valid = workdir / "valido.pdf"
    valid.write_bytes(b"%PDF-fake")

    result = import_candidates((workdir / "mancante.pdf", valid))

    assert [document.source for document in result.documents] == [valid.resolve()]
    assert len(result.errors) == 1
