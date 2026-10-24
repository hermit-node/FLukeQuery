"""Reusable Material-inspired QWidget controls for FLukeQuery.

Native Qt controls are retained for keyboard, IME, accessibility and focus support.
No dependency beyond PySide6. The app palette remains QSS-driven.
"""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGraphicsDropShadowEffect, QLineEdit,
    QPushButton, QTabBar, QTabWidget,
)


class MaterialButton(QPushButton):
    """Native button with animated hover elevation."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(38)
        self.setProperty("material", True)
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(0)
        self._shadow.setOffset(0, 3)
        self._shadow.setColor(QColor(255, 67, 191, 100))
        self.setGraphicsEffect(self._shadow)
        self._hover_anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._hover_anim.setDuration(150)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _animate_shadow(self, end):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._shadow.blurRadius())
        self._hover_anim.setEndValue(end)
        self._hover_anim.start()

    def enterEvent(self, event):
        if self.isEnabled():
            self._animate_shadow(16)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_shadow(0)
        super().leaveEvent(event)


class MaterialLineEdit(QLineEdit):
    """Native editor with consistent touch-sized hit target."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(39)
        self.setClearButtonEnabled(True)
        self.setProperty("material", True)


class MaterialComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(39)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("material", True)
        self.setMaxVisibleItems(14)


class MaterialCard(QFrame):
    """Surface container. Only explicit cards receive elevation."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("materialCard", True)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(23)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(8, 4, 15, 100))
        self.setGraphicsEffect(shadow)


class MaterialTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDocumentMode(True)
        self.setExpanding(False)
        self.setMinimumHeight(43)
        self.setDrawBase(False)
        self.setProperty("material", True)


class MaterialTabWidget(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabBar(MaterialTabBar(self))
        self.setDocumentMode(True)
