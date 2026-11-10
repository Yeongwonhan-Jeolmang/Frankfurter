"""
Filterable list of currencies with check boxes (Compare and Matrix tabs).
Replaces ~170 individual CTkCheckBox widgets with one QListWidget.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem


class CurrencyChecklist(QListWidget):
    changed = pyqtSignal()

    def __init__(self, codes, names: dict[str, str], checked=(), height: int = 220):
        super().__init__()
        self.setObjectName("Checklist")
        self.setFixedHeight(height)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setUniformItemSizes(True)
        self._names = names
        checked = set(checked)
        self.blockSignals(True)
        for code in codes:
            it = QListWidgetItem(f"{code}  {names.get(code, code)}")
            it.setData(Qt.ItemDataRole.UserRole, code)
            it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if code in checked else Qt.CheckState.Unchecked)
            self.addItem(it)
        self.blockSignals(False)
        self.itemChanged.connect(lambda _it: self.changed.emit())

    def mousePressEvent(self, e):
        # Clicking anywhere on the row toggles it (not just the tiny box)
        it = self.itemAt(e.position().toPoint())
        if it is not None and e.button() == Qt.MouseButton.LeftButton:
            on = it.checkState() == Qt.CheckState.Checked
            it.setCheckState(Qt.CheckState.Unchecked if on else Qt.CheckState.Checked)
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        self.mousePressEvent(e)  # a fast second click is still a toggle

    def selected(self) -> list[str]:
        """Checked codes in list (alphabetical) order."""
        out = []
        for i in range(self.count()):
            it = self.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                out.append(it.data(Qt.ItemDataRole.UserRole))
        return out

    def set_checked(self, code: str, on: bool = True) -> None:
        for i in range(self.count()):
            it = self.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == code:
                it.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
                return

    def clear_checks(self) -> None:
        self.blockSignals(True)
        for i in range(self.count()):
            self.item(i).setCheckState(Qt.CheckState.Unchecked)
        self.blockSignals(False)
        self.changed.emit()

    def apply_filter(self, text: str) -> None:
        text = text.upper()
        for i in range(self.count()):
            it = self.item(i)
            code = it.data(Qt.ItemDataRole.UserRole)
            show = not text or text in code or text in self._names.get(code, "").upper()
            it.setHidden(not show)
