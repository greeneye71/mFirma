from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def workdir() -> Path:
    """Workspace-local temporary directory (the sandbox blocks pytest tmp_path)."""
    path = Path(__file__).parent / "_runtime" / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)

