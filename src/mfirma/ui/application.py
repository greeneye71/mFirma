from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme, setThemeColor

from ..config import ConfigRepository
from .main_window import MFirmaQtWindow


def configure_application(application: QApplication) -> None:
    application.setApplicationName("mFirma")
    application.setApplicationDisplayName("mFirma — Firma PDF")
    application.setOrganizationName("mFirma")
    import reportlab

    fallback_path = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
    fallback_id = QFontDatabase.addApplicationFont(str(fallback_path))
    fallback_families = QFontDatabase.applicationFontFamilies(fallback_id)
    installed = set(QFontDatabase.families())
    if "Segoe UI" in installed:
        family = "Segoe UI"
    elif fallback_families:
        family = fallback_families[0]
    else:
        family = application.font().family()
    application.setFont(QFont(family, 10))
    setTheme(Theme.AUTO)
    setThemeColor(QColor("#2667D8"), save=False)


def run_application(
    arguments: Sequence[str] | None = None,
    repository: ConfigRepository | None = None,
) -> int:
    existing = QApplication.instance()
    owns_application = existing is None
    qt_arguments = [
        argument
        for argument in (arguments or sys.argv)
        if argument != "--qt-dashboard"
    ]
    application = existing or QApplication(qt_arguments)
    configure_application(application)
    window = MFirmaQtWindow(repository)
    application.setQuitOnLastWindowClosed(not window.tray_controller.available)
    window.shutdownReady.connect(application.quit)
    window.show()
    if owns_application:
        return application.exec()
    return 0


run_qt_dashboard = run_application
