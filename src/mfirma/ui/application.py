from __future__ import annotations

import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QMessageBox
from qfluentwidgets import FluentIcon, Theme, setTheme, setThemeColor

from ..config import ConfigRepository
from ..logging_setup import configure_logging, shutdown_logging
from .main_window import MFirmaQtWindow
from .single_instance import (
    ForwardStatus,
    RequestError,
    SingleInstanceServer,
    forward_file_request,
    instance_server_name,
    startup_pdf_paths,
)


LOGGER = logging.getLogger(__name__)


def configure_windows_identity() -> None:
    """Separa l'icona nella taskbar da quella dell'interprete Python."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        set_app_id = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        set_app_id.argtypes = [ctypes.c_wchar_p]
        set_app_id.restype = ctypes.c_long
        if set_app_id("mFirma.Desktop") != 0:
            LOGGER.warning("Identità Windows dell'applicazione non impostata")
    except (AttributeError, OSError):
        LOGGER.warning("Identità Windows dell'applicazione non disponibile")


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
    application.setWindowIcon(FluentIcon.CERTIFICATE.icon())


def run_application(
    arguments: Sequence[str] | None = None,
    repository: ConfigRepository | None = None,
) -> int:
    raw_arguments = list(arguments or sys.argv)
    startup_error = ""
    try:
        incoming_paths = startup_pdf_paths(raw_arguments)
    except RequestError as exc:
        incoming_paths = ()
        startup_error = str(exc)
    existing = QApplication.instance()
    owns_application = existing is None
    qt_arguments = [
        argument
        for argument in raw_arguments
        if argument != "--qt-dashboard"
    ]
    configure_windows_identity()
    application = existing or QApplication(qt_arguments)
    configure_application(application)
    config_path = repository.path if repository is not None else None
    single_instance = SingleInstanceServer(
        instance_server_name(config_path), application
    )
    if not single_instance.listen():
        status = (
            ForwardStatus.REJECTED
            if startup_error
            else forward_file_request(single_instance.server_name, incoming_paths)
        )
        if status is ForwardStatus.DELIVERED:
            return 0
        if (
            status is not ForwardStatus.NO_SERVER
            or not single_instance.remove_stale_and_listen()
        ):
            QMessageBox.warning(
                None,
                "mFirma già in esecuzione",
                startup_error
                or "Non è stato possibile inoltrare i documenti alla finestra aperta.",
            )
            return 2

    log_path = configure_logging()
    window = MFirmaQtWindow(repository, log_path=log_path)
    single_instance.filesReceived.connect(window.receive_external_paths)
    single_instance.requestRejected.connect(
        lambda message: LOGGER.warning("Richiesta IPC rifiutata: %s", message)
    )
    window.shutdownReady.connect(single_instance.close)
    application.setQuitOnLastWindowClosed(not window.tray_controller.available)
    window.shutdownReady.connect(application.quit)
    window.show()
    if startup_error:
        QTimer.singleShot(
            0,
            lambda message=startup_error: QMessageBox.warning(
                window, "Apertura PDF", message
            ),
        )
    if incoming_paths:
        QTimer.singleShot(
            0, lambda paths=incoming_paths: window.receive_external_paths(paths)
        )
    if owns_application:
        try:
            return application.exec()
        finally:
            shutdown_logging()
    return 0


run_qt_dashboard = run_application
