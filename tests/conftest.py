from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def workdir() -> Path:
    """Workspace-local temporary directory (the sandbox blocks pytest tmp_path)."""
    path = Path(__file__).parent / "_runtime" / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
