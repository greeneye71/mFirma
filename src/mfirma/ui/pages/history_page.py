from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, TitleLabel


class HistoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("historyPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(TitleLabel("Cronologia", self))
        message = BodyLabel(
            "La cronologia sarà disponibile quando verrà introdotto il relativo "
            "archivio persistente. Non vengono mostrati dati simulati.",
            self,
        )
        message.setWordWrap(True)
        layout.addWidget(message)
        layout.addStretch(1)
