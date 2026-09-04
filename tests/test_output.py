from pathlib import Path

import pytest

from mfirma.errors import OutputExistsError
from mfirma.output import create_temporary_output, destination_for, publish_temporary


def test_destination_keeps_source_and_adds_suffix(workdir: Path):
    source = workdir / "Contratto.PDF"
    source.write_bytes(b"originale")
    destination = destination_for(source)
    assert destination.name == "Contratto_firmato.PDF"
    assert source.read_bytes() == b"originale"


def test_temporary_publish_and_collision(workdir: Path):
    destination = workdir / "out.pdf"
    temporary = create_temporary_output(destination)
    temporary.write_bytes(b"firmato")
    publish_temporary(temporary, destination)
    assert destination.read_bytes() == b"firmato"
    with pytest.raises(OutputExistsError):
        create_temporary_output(destination)
