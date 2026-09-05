from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class SystemTrayController(QObject):
    showRequested = Signal()
    exitRequested = Signal()

    def __init__(
        self,
        icon: QIcon,
        parent=None,
        *,
        available_override: bool | None = None,
    ):
        super().__init__(parent)
        self.available = (
            QSystemTrayIcon.isSystemTrayAvailable()
            if available_override is None
            else available_override
        )
        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("mFirma — Firma PDF")
        self.menu = QMenu()
        self.open_action = QAction("Apri mFirma", self.menu)
        self.exit_action = QAction("Esci", self.menu)
        self.menu.addAction(self.open_action)
        self.menu.addSeparator()
        self.menu.addAction(self.exit_action)
        self.tray_icon.setContextMenu(self.menu)
        self.open_action.triggered.connect(self.showRequested)
        self.exit_action.triggered.connect(self.exitRequested)
        self.tray_icon.activated.connect(self._activated)
        if self.available:
            self.tray_icon.show()

    def set_busy(self, busy: bool) -> None:
        suffix = " — Firma in corso" if busy else " — Firma PDF"
        self.tray_icon.setToolTip(f"mFirma{suffix}")

    def set_shutting_down(self) -> None:
        self.open_action.setEnabled(False)
        self.exit_action.setEnabled(False)
        self.tray_icon.setToolTip("mFirma — Chiusura in corso")

    def notify_hidden(self) -> None:
        if self.available and QSystemTrayIcon.supportsMessages():
            self.tray_icon.showMessage(
                "mFirma resta attiva",
                "La finestra è stata nascosta. Usa l’icona nell’area di "
                "notifica per riaprirla.",
                QSystemTrayIcon.MessageIcon.Information,
                3500,
            )

    def hide(self) -> None:
        self.tray_icon.hide()

    @Slot(object)
    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.showRequested.emit()
