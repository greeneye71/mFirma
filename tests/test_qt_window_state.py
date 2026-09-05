from __future__ import annotations

import json

import pytest
from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QGuiApplication

from mfirma.config import AppConfig, ConfigRepository
from mfirma.ui.main_window import MFirmaQtWindow
from mfirma.ui.window_state import (
    WindowState,
    WindowStateRepository,
    fit_window_geometry,
)


def test_window_state_repository_is_atomic_and_contains_only_geometry(workdir):
    path = workdir / "window-state.json"
    repository = WindowStateRepository(path)
    state = WindowState(120, 80, 1180, 760, maximized=True)

    repository.save(state)

    assert repository.load() == state
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert set(raw) == {"x", "y", "width", "height", "maximized", "version"}
    assert "pin" not in path.read_text(encoding="utf-8").casefold()
    assert not list(workdir.glob("window-state-*.tmp"))


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"x": 0, "y": 0, "width": 50, "height": 760},
        {"x": 0, "y": 0, "width": 1180, "height": 760, "pin": "1234"},
        {
            "x": 0,
            "y": 0,
            "width": 1180,
            "height": 760,
            "maximized": "sì",
        },
    ],
)
def test_window_state_repository_rejects_invalid_data(workdir, payload):
    path = workdir / "window-state.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError):
        WindowStateRepository(path).load()


def test_saved_window_is_moved_inside_an_available_monitor():
    screens = (QRect(0, 0, 1920, 1040), QRect(1920, 0, 1920, 1040))

    restored = fit_window_geometry(
        WindowState(9000, 7000, 1180, 760),
        screens,
        minimum_size=QSize(900, 620),
    )

    assert restored == QRect(740, 280, 1180, 760)
    assert screens[0].contains(restored)


def test_saved_window_uses_monitor_with_largest_intersection():
    screens = (QRect(0, 0, 1920, 1040), QRect(1920, 0, 1920, 1040))

    restored = fit_window_geometry(
        WindowState(2100, 100, 1500, 900),
        screens,
        minimum_size=QSize(900, 620),
    )

    assert screens[1].contains(restored)
    assert restored.topLeft().x() >= 1920


def test_main_window_restores_and_saves_geometry(qtbot, workdir):
    config_repository = ConfigRepository(workdir / "config.json")
    config_repository.save(AppConfig())
    state_repository = WindowStateRepository(workdir / "window-state.json")
    saved = WindowState(9000, 7000, 1100, 700)
    state_repository.save(saved)
    window = MFirmaQtWindow(
        config_repository,
        window_state_repository=state_repository,
        tray_available=False,
        auto_scan=False,
    )
    qtbot.addWidget(window)
    expected = fit_window_geometry(
        saved,
        (screen.availableGeometry() for screen in QGuiApplication.screens()),
        minimum_size=window.minimumSize(),
    )

    assert window.geometry() == expected
    window.setGeometry(25, 35, 1000, 700)
    geometry_before_close = window.geometry()
    window.show()
    window.close()

    persisted = state_repository.load()
    assert persisted is not None
    assert persisted.x == geometry_before_close.x()
    assert persisted.y == geometry_before_close.y()
    assert persisted.width == geometry_before_close.width()
    assert persisted.height == geometry_before_close.height()


def test_maximized_window_remains_maximized_after_tray_restore(qtbot, workdir):
    config_repository = ConfigRepository(workdir / "config.json")
    config_repository.save(AppConfig())
    state_repository = WindowStateRepository(workdir / "window-state.json")
    state_repository.save(WindowState(20, 30, 1000, 700, maximized=True))
    window = MFirmaQtWindow(
        config_repository,
        window_state_repository=state_repository,
        tray_available=True,
        auto_scan=False,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(20)

    assert window._restore_maximized
    window.close()
    assert not window.isVisible()
    window.tray_controller.open_action.trigger()
    assert window._restore_maximized

    with qtbot.waitSignal(window.shutdownReady, timeout=1000):
        window.request_exit()
    assert state_repository.load().maximized
