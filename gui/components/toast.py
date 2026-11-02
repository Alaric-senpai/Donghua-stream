"""Bottom-right transient notification overlay."""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from ..motion import fade_in
from ..theme import T_EMERALD2, T_ROSE2


class Toast(QFrame):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setProperty("tone", "ok")
        self.setMaximumWidth(440)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.TextFormat.RichText)
        self._label.setMaximumWidth(390)
        lay.addWidget(self._label)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str, ok: bool = True, ms: int = 4200):
        self.setProperty("tone", "ok" if ok else "error")
        self.style().unpolish(self)
        self.style().polish(self)
        mark = "✔" if ok else "⚠"
        color = T_EMERALD2 if ok else T_ROSE2
        self._label.setText(
            f"<span style='color:{color}; font-weight:800'>{mark}</span>"
            f"&nbsp;&nbsp;{text}"
        )
        self.adjustSize()
        if self.width() > 440:
            self.setFixedWidth(440)
            self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
        fade_in(self, 140)
        self._timer.start(ms)

    def _reposition(self) -> None:
        host = self.parentWidget()
        if host is None:
            return
        self.move(max(16, host.width() - self.width() - 24),
                  max(16, host.height() - self.height() - 48))

    def resize_for(self, _host: QWidget):
        self._reposition()
