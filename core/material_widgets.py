"""Reusable Material-inspired native Qt widgets for FLukeQuery.

These extend QWidget controls (not web views), preserving keyboard shortcuts,
focus, input methods, accessibility metadata, and text editing semantics.
"""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QSize, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QFrame,
    QGraphicsDropShadowEffect, QLineEdit, QListView, QPushButton, QStyle,
    QStyleOptionButton, QStylePainter, QStyledItemDelegate, QTabBar, QTabWidget,
)


class MaterialButton(QPushButton):
    """Material-inspired filled/tonal/outline action with animated hover elevation."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(40)
        self.setProperty("material", True)
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(0)
        self._shadow.setOffset(0, 3)
        self._shadow.setColor(QColor(255, 67, 191, 85))
        self.setGraphicsEffect(self._shadow)
        self._hover_anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._hover_anim.setDuration(160)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _animate_shadow(self, radius: float):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._shadow.blurRadius())
        self._hover_anim.setEndValue(radius)
        self._hover_anim.start()

    def enterEvent(self, event):
        if self.isEnabled():
            self._animate_shadow(14)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_shadow(0)
        super().leaveEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if not self.isEnabled() and hasattr(self, "_hover_anim"):
            self._animate_shadow(0)


class MaterialLineEdit(QLineEdit):
    """Native single-line editor with touch-sized target and native clear action."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(42)
        self.setClearButtonEnabled(True)
        self.setProperty("material", True)


class _MaterialComboDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        result = super().sizeHint(option, index)
        result.setHeight(max(36, result.height()))
        return result


class MaterialComboBox(QComboBox):
    """A compact, keyboard-operable selector with a spaced popup list."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("material", True)
        self.setMaxVisibleItems(14)
        view = QListView(self)
        view.setUniformItemSizes(True)
        view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setView(view)
        self.setItemDelegate(_MaterialComboDelegate(self))


class MaterialCard(QFrame):
    """Tonal container. Shadow is deliberately subtle and never handles input."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("materialCard", True)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(19)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(11, 5, 22, 75))
        self.setGraphicsEffect(shadow)


class MaterialCheckBox(QCheckBox):
    """Custom indicator avoids Qt's sometimes invisible QSS checked glyph."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(31)
        self.setProperty("material", True)

    def paintEvent(self, event):
        option = QStyleOptionButton()
        self.initStyleOption(option)
        painter = QStylePainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Retain platform's label, mnemonics, focus behavior and font.
        painter.drawControl(QStyle.ControlElement.CE_CheckBoxLabel, option)
        indicator = self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, self)
        indicator.adjust(1, 1, -1, -1)
        if indicator.isEmpty():
            return
        colors = getattr(self.window(), "theme_colors", None)
        accent = QColor(colors.yellow if colors is not None else "#fff13f")
        border = QColor(colors.fuchsia if colors is not None else "#ff43bf")
        checked = self.checkState() != Qt.CheckState.Unchecked
        if not self.isEnabled():
            painter.setOpacity(0.4)
        painter.setPen(QPen(accent if self.hasFocus() else border, 1.7))
        painter.setBrush(accent if checked else QColor(0, 0, 0, 0))
        painter.drawRoundedRect(indicator, 5, 5)
        if checked:
            painter.setPen(QPen(QColor("#24152b"), 2.3, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            center = indicator.center()
            if self.checkState() == Qt.CheckState.PartiallyChecked:
                painter.drawLine(center.x() - 5, center.y(), center.x() + 5, center.y())
            else:
                painter.drawLine(center.x() - 5, center.y(), center.x() - 1, center.y() + 4)
                painter.drawLine(center.x() - 1, center.y() + 4, center.x() + 6, center.y() - 4)


class MaterialTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDocumentMode(True)
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setMinimumHeight(47)
        self.setProperty("material", True)


class MaterialTabWidget(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabBar(MaterialTabBar(self))
        self.setDocumentMode(True)
