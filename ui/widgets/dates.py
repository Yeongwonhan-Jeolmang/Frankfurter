"""
Date entry with a calendar drop-down. Replaces the tkcalendar pop-up with
Qt's built-in ``QCalendarWidget`` — no extra dependency.

The field stays a free-text YYYY-MM-DD line edit (rather than a QDateEdit)
because the Converter needs a *blank* value meaning "latest", and because
the tabs validate the text and flag bad input in red.
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QDate, QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QTextCharFormat
from PyQt6.QtWidgets import (
    QCalendarWidget,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ui.theme import *
from ui.widgets.common import make_button, set_error

MIN_DATE = date(1948, 1, 1)


class CalendarPopup(QFrame):
    """Frameless pop-up holding a calendar plus Today / Cancel buttons."""

    picked = pyqtSignal(str)

    def __init__(self, parent: QWidget, current: date):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("CalendarPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(PAD_SM, PAD_SM, PAD_SM, PAD_SM)
        lay.setSpacing(PAD_SM)

        cal = QCalendarWidget()
        cal.setGridVisible(False)
        cal.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        cal.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )
        cal.setHorizontalHeaderFormat(
            QCalendarWidget.HorizontalHeaderFormat.ShortDayNames
        )
        cal.setMinimumDate(QDate(MIN_DATE.year, MIN_DATE.month, MIN_DATE.day))
        t = date.today()
        cal.setMaximumDate(QDate(t.year, t.month, t.day))
        cal.setSelectedDate(QDate(current.year, current.month, current.day))

        hdr = QTextCharFormat()
        hdr.setForeground(QColor(ACCENT_GOLD))
        hdr.setBackground(QColor(BG_INPUT))
        cal.setHeaderTextFormat(hdr)
        wkend = QTextCharFormat()
        wkend.setForeground(QColor(TEXT_MUTED))
        for d in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
            cal.setWeekdayTextFormat(d, wkend)
        cal.clicked.connect(self._pick)
        cal.activated.connect(self._pick)
        lay.addWidget(cal)
        self._cal = cal

        row = QHBoxLayout()
        row.addWidget(make_button("Today", self._today, "outline", width=70))
        row.addStretch(1)
        row.addWidget(make_button("Cancel", self.close, "muted", width=70))
        lay.addLayout(row)

    def _pick(self, qd: QDate) -> None:
        self.picked.emit(qd.toString("yyyy-MM-dd"))
        self.close()

    def _today(self) -> None:
        self._pick(QDate.currentDate())

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)


class DateEntry(QWidget):
    """A YYYY-MM-DD line edit with a 📅 calendar button."""

    picked = pyqtSignal(str)

    def __init__(self, default: str = ""):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.entry = QLineEdit(default)
        self.entry.setPlaceholderText("YYYY-MM-DD")
        self.entry.setProperty("mono", True)
        self.entry.setMaxLength(10)
        self.entry.textEdited.connect(lambda _t: set_error(self.entry, False))
        lay.addWidget(self.entry, 1)
        self._btn = make_button(
            "📅", self.open_picker, "outline", width=34, tooltip="Pick a date"
        )
        lay.addWidget(self._btn)

    def open_picker(self) -> None:
        try:
            current = date.fromisoformat(self.get().strip())
        except ValueError:
            current = date.today()
        current = min(max(current, MIN_DATE), date.today())
        pop = CalendarPopup(self, current)
        pop.picked.connect(self._on_pick)
        pop.adjustSize()
        # Below the field, but kept on screen
        pos = self.mapToGlobal(QPoint(0, self.height() + 4))
        scr = self.screen().availableGeometry() if self.screen() else None
        if scr is not None:
            pos.setX(min(pos.x(), scr.right() - pop.width()))
            if pos.y() + pop.height() > scr.bottom():
                pos.setY(self.mapToGlobal(QPoint(0, 0)).y() - pop.height() - 4)
        pop.move(pos)
        pop.show()
        self._popup = pop

    def _on_pick(self, iso: str) -> None:
        self.set(iso)
        self.picked.emit(iso)

    # Same small API the tabs used with the Tk version
    def get(self) -> str:
        return self.entry.text()

    def set(self, text: str) -> None:
        self.entry.setText(text)
        set_error(self.entry, False)

    def flag_error(self, bad: bool = True) -> None:
        set_error(self.entry, bad)
