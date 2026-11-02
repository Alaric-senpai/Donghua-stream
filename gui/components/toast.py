"""Bottom-right transient notification overlay."""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from ..theme import T_EMERALD2


class Toast(QFrame):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(self._label)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str, ok: bool = True, ms: int = 4200):
        self._label.setText(
            f"<span style='color:{T_EMERALD2 if ok else '#ffb4ab'};font-weight:800'>"
            f"{'✔' if ok else '⚠'}</span>&nbsp;{text}"
        )
        self.adjustSize()
        host = self.parent() if self.parent() is not None else self
        self.move(host.width() - self.width() - 24, host.height() - self.height() - 64)
        self.show()
        self.raise_()
        self._timer.start(ms)

    def resize_for(self, host: QWidget):
        self.move(host.width() - self.width() - 24, host.height() - self.height() - 64)

