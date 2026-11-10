"""
Loading states: the pulsing skeleton overlay shown while a request is in
flight, and the braille spinner label used during start-up.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QLabel, QWidget

from ui.theme import *

FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class SkeletonOverlay(QWidget):
    """
    Covers *target* exactly while data is loading. It follows the target's
    size via an event filter, so it never disturbs the layout underneath.
    Call :meth:`start` before the request and :meth:`stop` when it finishes.
    """

    _WIDTHS = (0.85, 0.65, 0.78, 0.55, 0.82, 0.60, 0.72)

    def __init__(self, target: QWidget, rows: int = 7):
        super().__init__(target)
        self._target = target
        self._rows = rows
        self._frame = 0
        self._phase = False
        self._timer = QTimer(self)
        self._timer.setInterval(140)
        self._timer.timeout.connect(self._tick)
        self._font = qfont((FONT_MONO[0], 12))
        target.installEventFilter(self)
        self.hide()

    def eventFilter(self, obj, ev):
        if obj is self._target and ev.type() == QEvent.Type.Resize and self.isVisible():
            self.setGeometry(self._target.rect())
        return super().eventFilter(obj, ev)

    def start(self) -> None:
        self.setGeometry(self._target.rect())
        self.raise_()
        self.show()
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self.hide()

    @property
    def active(self) -> bool:
        return self.isVisible()

    def _tick(self) -> None:
        self._frame = (self._frame + 1) % len(FRAMES)
        self._phase = not self._phase
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(BG_DARK))
        p.setPen(QColor(ACCENT_GOLD))
        p.setFont(self._font)
        top = PAD_LG + 4
        p.drawText(
            QRectF(0, top, self.width(), 24),
            Qt.AlignmentFlag.AlignCenter,
            f"{FRAMES[self._frame]}  Loading data…",
        )
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(BG_HOVER if self._phase else BG_INPUT))
        x0 = PAD_LG * 3
        full = max(self.width() - 2 * x0, 40)
        y = top + 24 + PAD_MD
        for j in range(self._rows):
            w = full * self._WIDTHS[j % len(self._WIDTHS)]
            p.drawRoundedRect(QRectF(x0, y, w, 16), 4, 4)
            y += 24
        p.end()


class SpinnerLabel(QLabel):
    """A label whose text is prefixed with an animated braille spinner."""

    def __init__(self, text: str, font=FONT_HEADING, color: str = ACCENT_GOLD):
        super().__init__()
        self._text = text
        self._i = 0
        self.setFont(qfont(font))
        self.setStyleSheet(f"color: {color};")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timer = QTimer(self)
        self._timer.setInterval(90)
        self._timer.timeout.connect(self._tick)
        self._tick()
        self._timer.start()

    def _tick(self) -> None:
        self._i = (self._i + 1) % len(FRAMES)
        self.setText(f"{FRAMES[self._i]}  {self._text}")
