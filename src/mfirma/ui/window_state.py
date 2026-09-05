from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QRect, QSize


@dataclass(frozen=True, slots=True)
class WindowState:
    x: int
    y: int
    width: int
    height: int
    maximized: bool = False
    version: int = 1

    def validate(self) -> None:
        if self.version != 1:
            raise ValueError("Versione stato finestra non supportata")
        if not 100 <= self.width <= 32768 or not 100 <= self.height <= 32768:
            raise ValueError("Dimensioni finestra non valide")
        if abs(self.x) > 1_000_000 or abs(self.y) > 1_000_000:
            raise ValueError("Posizione finestra non valida")
        if not isinstance(self.maximized, bool):
            raise ValueError("Stato massimizzato non valido")

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "WindowState":
        allowed = {"x", "y", "width", "height", "maximized", "version"}
        unknown = set(raw) - allowed
        if unknown:
            raise ValueError("Lo stato finestra contiene campi sconosciuti")
        required = {"x", "y", "width", "height"}
        if not required.issubset(raw):
            raise ValueError("Lo stato finestra è incompleto")
        state = cls(
            x=int(raw["x"]),
            y=int(raw["y"]),
            width=int(raw["width"]),
            height=int(raw["height"]),
            maximized=raw.get("maximized", False),
            version=int(raw.get("version", 1)),
        )
        state.validate()
        return state


class WindowStateRepository:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> WindowState | None:
        if not self.path.exists():
            return None
        with self.path.open("r", encoding="utf-8") as stream:
            raw = json.load(stream)
        if not isinstance(raw, dict):
            raise ValueError("Lo stato finestra deve essere un oggetto JSON")
        return WindowState.from_dict(raw)

    def save(self, state: WindowState) -> None:
        state.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix="window-state-",
            suffix=".tmp",
            dir=self.path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(asdict(state), stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)


def fit_window_geometry(
    state: WindowState,
    available_screens: Iterable[QRect],
    *,
    minimum_size: QSize,
) -> QRect:
    screens = tuple(available_screens)
    if not screens:
        return QRect(state.x, state.y, state.width, state.height)
    saved = QRect(state.x, state.y, state.width, state.height)
    screen = max(
        screens,
        key=lambda candidate: _intersection_area(saved, candidate),
    )
    if _intersection_area(saved, screen) == 0:
        screen = screens[0]
    width = max(minimum_size.width(), min(state.width, screen.width()))
    height = max(minimum_size.height(), min(state.height, screen.height()))
    maximum_x = screen.x() + max(0, screen.width() - width)
    maximum_y = screen.y() + max(0, screen.height() - height)
    x = min(max(state.x, screen.x()), maximum_x)
    y = min(max(state.y, screen.y()), maximum_y)
    return QRect(x, y, width, height)


def _intersection_area(first: QRect, second: QRect) -> int:
    intersection = first.intersected(second)
    return max(0, intersection.width()) * max(0, intersection.height())
