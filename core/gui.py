"""FLukeQuery — native PySide6 HTTP request workbench."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sys
from threading import Event

from PySide6.QtCore import QObject, QRunnable, QSettings, Qt, QThreadPool, Signal
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QTextCharFormat, QSyntaxHighlighter
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QCheckBox, QColorDialog, QComboBox, QDialog, QDoubleSpinBox,
    QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QStackedWidget,
    QSlider, QStatusBar, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from .core import SUPPORTED_METHODS, RequestCancelled, RequestSpec, ResponseData, curl_command, execute, format_content
from .theme import PRESETS, STYLE, ThemeColors, blend, normalize_hex, style_for
from .material_widgets import (MaterialButton as QPushButton, MaterialLineEdit as QLineEdit,
                               MaterialComboBox as QComboBox, MaterialCard, MaterialTabWidget as QTabWidget,
                               MaterialCheckBox as QCheckBox)

DATA_ROOT = Path(os.getenv("APPDATA", Path.home() / ".config"))
APP_DIR = DATA_ROOT / "FLukeQuery"
COLLECTIONS = APP_DIR / "requests.json"
LEGACY_COLLECTIONS = DATA_ROOT / "VoltHTTP" / "requests.json"


def label(text: str, name: str = "") -> QLabel:
    item = QLabel(text)
    if name:
        item.setObjectName(name)
    return item


def button(text: str, handler, variant: str = "") -> QPushButton:
    item = QPushButton(text)
    if variant:
        item.setObjectName(variant)
    item.clicked.connect(handler)
    return item


def layout_column(widget: QWidget, padding: int = 14, spacing: int = 10) -> QVBoxLayout:
    lay = QVBoxLayout(widget)
    lay.setContentsMargins(padding, padding, padding, padding)
    lay.setSpacing(spacing)
    return lay


class PairTable(QWidget):
    """Editable duplicate-preserving query/header/form pairs."""
    def __init__(self, key_hint: str, value_hint: str, parent=None):
        super().__init__(parent)
        outer = layout_column(self, 9, 8)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([key_hint, value_hint])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        outer.addWidget(self.table, 1)
        row = QHBoxLayout()
        row.addWidget(button("＋ Add row", lambda: self.add_row()))
        row.addWidget(button("− Remove", self.remove_selected))
        row.addStretch()
        outer.addLayout(row)
        self.add_row()

    def add_row(self, key: str = "", value: str = ""):
        i = self.table.rowCount()
        self.table.insertRow(i)
        self.table.setItem(i, 0, QTableWidgetItem(key))
        self.table.setItem(i, 1, QTableWidgetItem(value))
        self.table.setRowHeight(i, 34)

    def remove_selected(self):
        indexes = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        for row in indexes:
            self.table.removeRow(row)
        if self.table.rowCount() == 0:
            self.add_row()

    def rows(self) -> list[list[str]]:
        output = []
        for i in range(self.table.rowCount()):
            a = self.table.item(i, 0)
            b = self.table.item(i, 1)
            key = a.text() if a else ""
            value = b.text() if b else ""
            if key.strip():
                output.append([key, value])
        return output

    def set_rows(self, items: list[list[str]]):
        self.table.setRowCount(0)
        for key, value in items:
            self.add_row(key, value)
        if not items:
            self.add_row()


class JsonHighlighter(QSyntaxHighlighter):
    """Lightweight JSON token coloring without external dependencies."""
    def __init__(self, document, colors: ThemeColors):
        super().__init__(document)
        self.set_palette(colors)

    def set_palette(self, colors: ThemeColors):
        import re
        self.patterns = [
            (re.compile(r'"(?:\\.|[^"\\])*"(?=\s*:)'), QColor(colors.yellow)),
            (re.compile(r'(?<=:)\s*"(?:\\.|[^"\\])*"'), QColor(blend(colors.fuchsia, "#ffffff", 0.48))),
            (re.compile(r'\b(?:true|false|null)\b'), QColor("#b6aeff")),
            (re.compile(r'(?<![\w.])-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?'), QColor("#7ce2d1")),
        ]
        self.rehighlight()

    def highlightBlock(self, text: str):
        for pattern, color in self.patterns:
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class WorkerSignals(QObject):
    done = Signal(object, object)  # RequestSpec, ResponseData
    failed = Signal(object, str)  # RequestSpec, message
    cancelled = Signal()


class HttpWorker(QRunnable):
    def __init__(self, spec: RequestSpec):
        super().__init__()
        self.spec = copy.deepcopy(spec)
        self.cancel_event = Event()
        self.signals = WorkerSignals()

    def run(self):
        try:
            outcome = execute(self.spec, self.cancel_event)
        except RequestCancelled:
            self.signals.cancelled.emit()
        except Exception as exc:
            self.signals.failed.emit(self.spec, f"{type(exc).__name__}: {exc}")
        else:
            self.signals.done.emit(self.spec, outcome)


class ThemeDialog(QDialog):
    """Configures one of three themes or custom yellow / fuchsia / background colors."""
    FIELDS = (("yellow", "Yellow accent"), ("fuchsia", "Fuchsia accent"), ("background", "Background"))

    def __init__(self, preset: str, colors: ThemeColors,
                 glass: int = 55, window_opacity: int = 100, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FLukeQuery · Theme")
        self.setMinimumWidth(345)
        self.colors = colors
        layout = QVBoxLayout(self)
        intro = QLabel("Choose a palette, or customize the three base colors.\nThe theme is saved between launches.")
        layout.addWidget(intro)
        row = QFormLayout()
        self.preset_box = QComboBox()
        self.preset_box.addItems([*PRESETS, "Custom"])
        self.preset_box.setCurrentText(preset if preset in PRESETS else "Custom")
        self.preset_box.currentTextChanged.connect(self._preset_changed)
        row.addRow("Palette", self.preset_box)
        self.swatches = {}
        for key, caption in self.FIELDS:
            pick = QPushButton()
            pick.setMinimumHeight(38)
            pick.clicked.connect(lambda checked=False, k=key: self._pick(k))
            self.swatches[key] = pick
            row.addRow(caption, pick)
        layout.addLayout(row)
        layout.addWidget(QLabel("Yellow: action/focus  ·  Fuchsia: highlights  ·  Background: base"))
        opacity_form = QFormLayout()
        self.glass_slider = QSlider(Qt.Orientation.Horizontal)
        self.glass_slider.setRange(0, 85)
        self.glass_slider.setSingleStep(5)
        self.glass_slider.setPageStep(10)
        self.glass_slider.setValue(max(0, min(85, int(glass))))
        self.glass_slider.setToolTip("Translucency of panels, buttons and fields. Text stays opaque.")
        self.glass_label = QLabel(f"{self.glass_slider.value()}%")
        self.glass_label.setMinimumWidth(37)
        glass_row = QHBoxLayout()
        glass_row.addWidget(self.glass_slider, 1)
        glass_row.addWidget(self.glass_label)
        opacity_form.addRow("Surface glass", glass_row)
        self.glass_slider.valueChanged.connect(lambda value: self.glass_label.setText(f"{value}%"))

        self.window_slider = QSlider(Qt.Orientation.Horizontal)
        self.window_slider.setRange(85, 100)
        self.window_slider.setValue(max(85, min(100, int(window_opacity))))
        self.window_slider.setToolTip("Windows-level whole-window opacity; also fades text and controls.")
        self.window_label = QLabel(f"{self.window_slider.value()}%")
        self.window_label.setMinimumWidth(37)
        window_row = QHBoxLayout()
        window_row.addWidget(self.window_slider, 1)
        window_row.addWidget(self.window_label)
        opacity_form.addRow("Window opacity", window_row)
        self.window_slider.valueChanged.connect(lambda value: self.window_label.setText(f"{value}%"))
        layout.addLayout(opacity_form)
        hint = QLabel("Surface glass reveals the layered FLukeQuery backdrop. "
                      "Window opacity allows the desktop behind to show through, "
                      "but also fades text; 100% retains sharp text.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        actions.accepted.connect(self.accept)
        actions.rejected.connect(self.reject)
        layout.addWidget(actions)
        self._refresh_swatches()

    def _preset_changed(self, name: str):
        if name in PRESETS:
            self.colors = PRESETS[name]
            self._refresh_swatches()

    def _pick(self, field: str):
        chosen = QColorDialog.getColor(QColor(getattr(self.colors, field)), self, f"Choose {field}")
        if not chosen.isValid():
            return
        values = {key: getattr(self.colors, key) for key, _ in self.FIELDS}
        values[field] = normalize_hex(chosen.name())
        self.colors = ThemeColors(**values)
        self.preset_box.blockSignals(True)
        self.preset_box.setCurrentText("Custom")
        self.preset_box.blockSignals(False)
        self._refresh_swatches()

    def _refresh_swatches(self):
        for field, _ in self.FIELDS:
            color = getattr(self.colors, field)
            rgb = QColor(color)
            ink = "#211226" if rgb.lightness() > 135 else "#ffffff"
            widget = self.swatches[field]
            widget.setText(color.upper())
            widget.setStyleSheet(f"QPushButton {{ background: {color}; color: {ink}; border: 1px solid #ffffff; border-radius: 8px; font-weight: 900; }}")


class FLukeQueryWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FLukeQuery · Request Studio")
        self.resize(1520, 930)
        self.setMinimumSize(1000, 670)
        self.settings = QSettings("FLukeQuery", "FLukeQuery")
        # Preserve the user's existing theme choices under the former application ID.
        if not self.settings.allKeys():
            previous = QSettings("VoltHTTP", "VoltHTTP")
            for key in previous.allKeys():
                self.settings.setValue(key, previous.value(key))
            self.settings.sync()
        self.theme_preset = str(self.settings.value("theme/preset", "Vivid"))
        def read_setting_int(key: str, default: int, low: int, high: int) -> int:
            try:
                return max(low, min(high, int(self.settings.value(key, default))))
            except (ValueError, TypeError):
                return default
        self.glass_percent = read_setting_int("theme/glass", 55, 0, 85)
        self.window_opacity_percent = read_setting_int("theme/window_opacity", 100, 85, 100)
        try:
            self.theme_colors = ThemeColors(*[
                normalize_hex(str(self.settings.value("theme/" + key, getattr(PRESETS["Vivid"], key))))
                for key in ("yellow", "fuchsia", "background")
            ])
        except (ValueError, TypeError):
            self.theme_preset, self.theme_colors = "Vivid", PRESETS["Vivid"]
        if self.theme_preset in PRESETS and self.settings.value("theme/yellow") is None:
            self.theme_colors = PRESETS[self.theme_preset]
        QApplication.instance().setStyleSheet(style_for(self.theme_colors, self.glass_percent))
        self.setWindowOpacity(self.window_opacity_percent / 100.0)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.active_worker: HttpWorker | None = None
        self.result: ResponseData | None = None
        self.history: list[RequestSpec] = []
        self.saved: list[dict] = self._read_saved()
        self._build()
        self._wire_keys()
        self._refresh_sidebar()
        self.statusBar().showMessage("Ready · HTTPX engine · credentials stay in memory")

    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        banner = QFrame()
        banner.setObjectName("topbar")
        top = QHBoxLayout(banner)
        top.setContentsMargins(25, 15, 25, 15)
        mark = QVBoxLayout()
        mark.setSpacing(1)
        mark.addWidget(label("FLUKE  /  QUERY", "brand"))
        mark.addWidget(label("REQUEST STUDIO   ·   HTTPX ENGINE", "brandNote"))
        top.addLayout(mark)
        top.addStretch()
        top.addWidget(button("Theme ✦", self.configure_theme))
        top.addWidget(button("Import", self.import_request))
        top.addWidget(button("Copy cURL", self.copy_curl))
        top.addWidget(button("Save request", self.save_request, "pinkButton"))
        main.addWidget(banner)

        request_strip = QFrame()
        strip = QHBoxLayout(request_strip)
        strip.setContentsMargins(18, 16, 18, 16)
        strip.setSpacing(10)
        self.method = QComboBox()
        self.method.setObjectName("methodSelector")
        self.method.setAccessibleName("HTTP method")
        self.method.addItems(SUPPORTED_METHODS)
        self.method.currentTextChanged.connect(self._method_changed)
        self.method.setFixedWidth(143)
        self.method.setFixedHeight(45)
        strip.addWidget(self.method)
        self.url = QLineEdit("https://httpbin.org/get")
        self.url.setPlaceholderText("https://api.example.com/v1/resource")
        self.url.setAccessibleName("Request URL")
        self.url.setFixedHeight(45)
        strip.addWidget(self.url, 1)
        self.send = button("➜  Send", self.send_request, "sendButton")
        self.send.setMinimumWidth(115)
        self.send.setFixedHeight(45)
        strip.addWidget(self.send)
        self.stop = button("Cancel", self.cancel_request)
        self.stop.setFixedHeight(45)
        self.stop.setEnabled(False)
        strip.addWidget(self.stop)
        main.addWidget(request_strip)

        overall = QSplitter(Qt.Orientation.Horizontal)
        overall.setChildrenCollapsible(False)
        overall.setHandleWidth(11)
        main.addWidget(overall, 1)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        side = layout_column(self.sidebar, 15, 9)
        side.addWidget(label("SAVED REQUESTS", "sectionTitle"))
        self.saved_list = QListWidget()
        self.saved_list.itemClicked.connect(self.load_sidebar_item)
        side.addWidget(self.saved_list, 3)
        side_button_row = QHBoxLayout()
        side_button_row.addWidget(button("Delete", self.delete_saved))
        side_button_row.addWidget(button("Export", self.export_request))
        side.addLayout(side_button_row)
        side.addSpacing(15)
        side.addWidget(label("THIS SESSION", "sectionTitle"))
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.load_sidebar_item)
        side.addWidget(self.history_list, 2)
        side.addWidget(label("History isn't written to disk.\nSaved requests exclude auth secrets.", "hint"))
        overall.addWidget(self.sidebar)

        work_area = QSplitter(Qt.Orientation.Horizontal)
        work_area.setChildrenCollapsible(False)
        work_area.setHandleWidth(13)
        overall.addWidget(work_area)
        self.request_panel = MaterialCard()
        self.request_panel.setObjectName("panel")
        req_layout = layout_column(self.request_panel, 17, 11)
        req_layout.addWidget(label("REQUEST CONFIGURATION", "sectionTitle"))
        self.request_tabs = QTabWidget()
        req_layout.addWidget(self.request_tabs, 1)
        self._make_request_tabs()
        self.request_panel.setMinimumWidth(360)
        work_area.addWidget(self.request_panel)

        self.response_panel = MaterialCard()
        self.response_panel.setObjectName("responsePanel")
        resp_layout = layout_column(self.response_panel, 17, 11)
        heading = QHBoxLayout()
        heading.addWidget(label("RESPONSE INSPECTOR", "sectionTitle"))
        heading.addStretch()
        self.response_state = label("NOT SENT", "responseState")
        heading.addWidget(self.response_state)
        resp_layout.addLayout(heading)
        meta = QHBoxLayout()
        self.time_label = label("— ms", "hint")
        self.size_label = label("— bytes", "hint")
        self.version_label = label("HTTP / —", "hint")
        for it in (self.time_label, self.size_label, self.version_label):
            meta.addWidget(it)
            meta.addSpacing(15)
        meta.addStretch()
        resp_layout.addLayout(meta)
        self.response_tabs = QTabWidget()
        resp_layout.addWidget(self.response_tabs, 1)
        self._make_response_tabs()
        self.response_panel.setMinimumWidth(375)
        work_area.addWidget(self.response_panel)
        overall.setSizes([220, 1280])
        work_area.setSizes([590, 690])
        self.setStatusBar(QStatusBar())

    def _make_request_tabs(self):
        self.params = PairTable("Parameter", "Value")
        self.headers = PairTable("Header", "Value")
        self.headers.set_rows([["Accept", "application/json"]])
        self.request_tabs.addTab(self.params, "Params")
        self.request_tabs.addTab(self.headers, "Headers")

        body_tab = QWidget()
        bl = layout_column(body_tab, 13)
        bl.addWidget(label("BODY CONTENT TYPE", "sectionTitle"))
        self.body_mode = QComboBox()
        self.body_mode.addItems(["None", "JSON", "Text", "Form"])
        bl.addWidget(self.body_mode)
        self.body_stack = QStackedWidget()
        self.body_stack.addWidget(label("No request body · Suitable for GET / HEAD.", "hint"))
        self.json_editor = QPlainTextEdit()
        self.json_editor.setPlaceholderText('{\n  "message": "Hello world"\n}')
        self.json_highlighter = JsonHighlighter(self.json_editor.document(), self.theme_colors)
        self.body_stack.addWidget(self.json_editor)
        self.text_editor = QPlainTextEdit()
        self.text_editor.setPlaceholderText("Raw UTF-8 text payload")
        self.body_stack.addWidget(self.text_editor)
        self.form = PairTable("Field", "Value")
        self.body_stack.addWidget(self.form)
        self.body_mode.currentIndexChanged.connect(self.body_stack.setCurrentIndex)
        bl.addWidget(self.body_stack, 1)
        bl.addWidget(label("QUERY (RFC 10008) uses a body and requires Content-Type.\nJSON is validated; Form is URL-encoded.", "hint"))
        self.request_tabs.addTab(body_tab, "Body")

        auth_tab = QWidget()
        authlay = layout_column(auth_tab, 13, 12)
        authlay.addWidget(label("AUTHENTICATION", "sectionTitle"))
        self.auth_mode = QComboBox()
        self.auth_mode.addItems(["None", "Bearer", "Basic"])
        authlay.addWidget(self.auth_mode)
        self.auth_stack = QStackedWidget()
        self.auth_stack.addWidget(label("No automatic authorization header.", "hint"))
        bearer = QWidget()
        bearerlay = layout_column(bearer, 0)
        bearerlay.addWidget(label("Bearer token"))
        self.bearer_token = QLineEdit()
        self.bearer_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.bearer_token.setPlaceholderText("Token (not saved)")
        bearerlay.addWidget(self.bearer_token)
        bearerlay.addStretch()
        self.auth_stack.addWidget(bearer)
        basic = QWidget()
        basiclay = layout_column(basic, 0)
        basiclay.addWidget(label("Username"))
        self.basic_user = QLineEdit()
        basiclay.addWidget(self.basic_user)
        basiclay.addWidget(label("Password"))
        self.basic_pass = QLineEdit()
        self.basic_pass.setEchoMode(QLineEdit.EchoMode.Password)
        basiclay.addWidget(self.basic_pass)
        basiclay.addStretch()
        self.auth_stack.addWidget(basic)
        self.auth_mode.currentIndexChanged.connect(self.auth_stack.setCurrentIndex)
        authlay.addWidget(self.auth_stack, 1)
        authlay.addWidget(label("Credentials stay in memory only; saved requests omit secrets.", "hint"))
        self.request_tabs.addTab(auth_tab, "Auth")

        opt = QWidget()
        optlay = layout_column(opt, 14, 13)
        optlay.addWidget(label("NETWORK OPTIONS", "sectionTitle"))
        timeout_row = QHBoxLayout()
        timeout_row.addWidget(label("Timeout (seconds)"))
        self.timeout = QDoubleSpinBox()
        self.timeout.setRange(0.5, 300)
        self.timeout.setValue(30)
        self.timeout.setSingleStep(5)
        timeout_row.addWidget(self.timeout)
        optlay.addLayout(timeout_row)
        self.follow_redirects = QCheckBox("Follow HTTP redirects")
        self.follow_redirects.setChecked(True)
        optlay.addWidget(self.follow_redirects)
        self.verify_tls = QCheckBox("Verify TLS certificates (recommended)")
        self.verify_tls.setChecked(True)
        optlay.addWidget(self.verify_tls)
        optlay.addWidget(label("Proxy URL (optional)", "sectionTitle"))
        self.proxy = QLineEdit()
        self.proxy.setPlaceholderText("http://127.0.0.1:8080")
        optlay.addWidget(self.proxy)
        optlay.addWidget(label("HTTPS verification can be disabled for local testing;\nleave enabled for real endpoints.", "hint"))
        optlay.addStretch()
        self.request_tabs.addTab(opt, "Options")

    def _make_response_tabs(self):
        body = QWidget()
        body_layout = layout_column(body, 8, 8)
        tools = QHBoxLayout()
        self.pretty = QCheckBox("Pretty JSON")
        self.pretty.setChecked(True)
        self.pretty.toggled.connect(self.render_response)
        tools.addWidget(self.pretty)
        tools.addStretch()
        self.find = QLineEdit()
        self.find.setPlaceholderText("Find in body...")
        self.find.setMaximumWidth(160)
        self.find.returnPressed.connect(self.find_in_body)
        tools.addWidget(self.find)
        tools.addWidget(button("Copy", self.copy_response))
        tools.addWidget(button("Save as…", self.save_response))
        body_layout.addLayout(tools)
        self.response_body = QPlainTextEdit()
        self.response_body.setReadOnly(True)
        self.response_body.setPlaceholderText("Press Send to inspect the response.")
        self.response_highlighter = JsonHighlighter(self.response_body.document(), self.theme_colors)
        body_layout.addWidget(self.response_body, 1)
        self.preview_info = label("Preview limit: 6 MiB; full binary/downloads are intentionally not buffered.", "hint")
        body_layout.addWidget(self.preview_info)
        self.response_tabs.addTab(body, "Body")
        self.response_headers = QPlainTextEdit()
        self.response_headers.setReadOnly(True)
        self.response_tabs.addTab(self.response_headers, "Headers")
        self.response_cookies = QPlainTextEdit()
        self.response_cookies.setReadOnly(True)
        self.response_tabs.addTab(self.response_cookies, "Cookies")
        self.response_redirects = QPlainTextEdit()
        self.response_redirects.setReadOnly(True)
        self.response_tabs.addTab(self.response_redirects, "Redirects")

    def configure_theme(self):
        dialog = ThemeDialog(self.theme_preset, self.theme_colors,
                             self.glass_percent, self.window_opacity_percent, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.theme_colors = dialog.colors
        self.theme_preset = dialog.preset_box.currentText()
        self.glass_percent = dialog.glass_slider.value()
        self.window_opacity_percent = dialog.window_slider.value()
        for key in ("yellow", "fuchsia", "background"):
            self.settings.setValue("theme/" + key, getattr(self.theme_colors, key))
        self.settings.setValue("theme/preset", self.theme_preset)
        self.settings.setValue("theme/glass", self.glass_percent)
        self.settings.setValue("theme/window_opacity", self.window_opacity_percent)
        QApplication.instance().setStyleSheet(style_for(self.theme_colors, self.glass_percent))
        self.setWindowOpacity(self.window_opacity_percent / 100.0)
        self.json_highlighter.set_palette(self.theme_colors)
        self.response_highlighter.set_palette(self.theme_colors)
        self.statusBar().showMessage(f"Theme applied: {self.theme_preset} · preferences saved")

    def _method_changed(self, method: str):
        if method == "QUERY" and self.body_mode.currentText() == "None":
            # QUERY has an explicit representation/media type unlike GET.
            self.body_mode.setCurrentText("JSON")
            if not self.json_editor.toPlainText().strip():
                self.json_editor.setPlainText("{}")
            self.request_tabs.setCurrentIndex(2)
            self.statusBar().showMessage("QUERY is safe/idempotent · edit the JSON body or select Text/Form")

    def _wire_keys(self):
        for title, sequence, fn in [
            ("Send request", "Ctrl+Return", self.send_request),
            ("Send request F5", "F5", self.send_request),
            ("Save request", "Ctrl+S", self.save_request),
            ("Focus address", "Ctrl+L", self.url.setFocus),
            ("Copy cURL", "Ctrl+Shift+C", self.copy_curl),
        ]:
            act = QAction(title, self)
            act.setShortcut(QKeySequence(sequence))
            act.triggered.connect(fn)
            self.addAction(act)

    def current_spec(self) -> RequestSpec:
        mode = self.body_mode.currentText()
        return RequestSpec(
            method=self.method.currentText(),
            url=self.url.text(),
            params=self.params.rows(),
            headers=self.headers.rows(),
            body_mode=mode,
            body_text=(self.json_editor if mode == "JSON" else self.text_editor).toPlainText(),
            form=self.form.rows(),
            auth_mode=self.auth_mode.currentText(),
            username=self.basic_user.text(),
            password=self.basic_pass.text(),
            token=self.bearer_token.text(),
            timeout=self.timeout.value(),
            follow_redirects=self.follow_redirects.isChecked(),
            verify_tls=self.verify_tls.isChecked(),
            proxy=self.proxy.text(),
        )

    def load_spec(self, spec: RequestSpec):
        self.method.setCurrentText(spec.method)
        self.url.setText(spec.url)
        self.params.set_rows(spec.params)
        self.headers.set_rows(spec.headers)
        self.body_mode.setCurrentText(spec.body_mode)
        self.json_editor.setPlainText(spec.body_text if spec.body_mode == "JSON" else "")
        self.text_editor.setPlainText(spec.body_text if spec.body_mode == "Text" else "")
        self.form.set_rows(spec.form)
        self.auth_mode.setCurrentText(spec.auth_mode)
        self.basic_user.setText(spec.username)
        self.basic_pass.setText(spec.password)
        self.bearer_token.setText(spec.token)
        self.timeout.setValue(spec.timeout)
        self.follow_redirects.setChecked(spec.follow_redirects)
        self.verify_tls.setChecked(spec.verify_tls)
        self.proxy.setText(spec.proxy)
        self.statusBar().showMessage("Request loaded · review credentials and press Send")

    def send_request(self):
        if self.active_worker is not None:
            return
        spec = self.current_spec()
        # Fail fast on bad URLs, JSON, timeout, and credentials before allocating a thread.
        try:
            from .core import prepare
            prepare(spec)
        except Exception as exc:
            QMessageBox.warning(self, "Invalid request", str(exc))
            return
        worker = HttpWorker(spec)
        self.active_worker = worker
        worker.signals.done.connect(self._request_done)
        worker.signals.failed.connect(self._request_failed)
        worker.signals.cancelled.connect(self._request_cancelled)
        self.send.setEnabled(False)
        self.stop.setEnabled(True)
        self.response_state.setText("SENDING …")
        self.response_state.setStyleSheet("color: #ffe663; font-weight: 800; padding: 6px;")
        self.statusBar().showMessage(f"Sending {spec.method} {spec.url} …")
        self.pool.start(worker)

    def cancel_request(self):
        if self.active_worker:
            self.active_worker.cancel_event.set()
            self.statusBar().showMessage("Cancellation requested · waiting for active network operation")

    def _end_work(self):
        self.active_worker = None
        self.send.setEnabled(True)
        self.stop.setEnabled(False)

    def _request_done(self, spec: RequestSpec, result: ResponseData):
        self._end_work()
        self.result = result
        self.history.insert(0, spec)
        self.history = self.history[:35]
        self._refresh_sidebar()
        self.response_state.setText(f"{result.status}  {result.reason}")
        col = "#a2f5bd" if result.status < 400 else "#ffc171" if result.status < 500 else "#ff8aa6"
        self.response_state.setStyleSheet(f"color: {col}; font-weight: 900; font-size: 14px; padding: 6px;")
        self.time_label.setText(f"◷  {result.elapsed_ms:,.0f} ms")
        self.size_label.setText(f"▣  {len(result.content):,} bytes" + (" +" if result.preview_truncated else ""))
        self.version_label.setText(result.http_version)
        self.response_headers.setPlainText("\n".join(f"{k}: {v}" for k, v in result.headers))
        self.response_cookies.setPlainText("\n".join(f"{k}: {v}" for k, v in result.cookies) or "No response cookies")
        self.response_redirects.setPlainText("\n".join(result.redirects) or "No redirects" )
        self.render_response()
        self.statusBar().showMessage(f"Received {result.status} from {result.final_url} in {result.elapsed_ms:.0f} ms")

    def _request_failed(self, spec: RequestSpec, message: str):
        self._end_work()
        self.result = None
        self.response_state.setText("NETWORK ERROR")
        self.response_state.setStyleSheet("color: #ff8aa6; font-weight: 900; padding: 6px;")
        self.response_body.setPlainText(message)
        self.statusBar().showMessage("Request failed · " + message[:210])

    def _request_cancelled(self):
        self._end_work()
        self.result = None
        self.response_state.setText("CANCELLED")
        self.statusBar().showMessage("Request cancelled")

    def render_response(self):
        if self.result is None:
            return
        view, is_json = format_content(self.result, self.pretty.isChecked())
        self.response_body.setPlainText(view)
        # Highlight only formatted JSON to avoid coloring arbitrary text.
        self.response_highlighter.setDocument(self.response_body.document() if is_json else None)
        if self.result.preview_truncated:
            self.preview_info.setText("⚠ Preview truncated at 6 MiB. Save as exports the buffered preview only.")
        else:
            self.preview_info.setText(f"{self.result.content_type or 'Unknown content type'}   ·   {len(self.result.content):,} bytes received")

    def find_in_body(self):
        value = self.find.text()
        if value:
            if not self.response_body.find(value):
                cursor = self.response_body.textCursor()
                cursor.movePosition(cursor.MoveOperation.Start)
                self.response_body.setTextCursor(cursor)
                self.response_body.find(value)

    def copy_response(self):
        QApplication.clipboard().setText(self.response_body.toPlainText())
        self.statusBar().showMessage("Response preview copied")

    def save_response(self):
        if self.result is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save response (buffered data)", "response.bin", "All files (*)")
        if path:
            try:
                Path(path).write_bytes(self.result.content)
            except OSError as exc:
                QMessageBox.critical(self, "Save failed", str(exc))
            else:
                self.statusBar().showMessage("Saved buffered response bytes to " + path)

    def copy_curl(self):
        try:
            command = curl_command(self.current_spec())
        except Exception as exc:
            QMessageBox.warning(self, "Cannot generate command", str(exc))
            return
        QApplication.clipboard().setText(command)
        self.statusBar().showMessage("Copied POSIX cURL command (sensitive headers/auth omitted; for Git Bash or WSL)")

    def _read_saved(self) -> list[dict]:
        # The former directory remains untouched. A new save writes FLukeQuery.
        source = COLLECTIONS if COLLECTIONS.exists() else LEGACY_COLLECTIONS
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (FileNotFoundError, ValueError, OSError):
            return []

    def _write_saved(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        temporary = COLLECTIONS.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.saved, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(COLLECTIONS)

    def save_request(self):
        title, ok = QInputDialog.getText(self, "Save request", "Request name", text=self.url.text().split("?")[0][-45:])
        if not ok or not title.strip():
            return
        entry = {"name": title.strip(), "request": self.current_spec().export(redact=True)}
        prior = next((idx for idx, old in enumerate(self.saved) if old.get("name") == title.strip()), None)
        if prior is not None:
            self.saved[prior] = entry
        else:
            self.saved.append(entry)
        try:
            self._write_saved()
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self._refresh_sidebar()
        self.statusBar().showMessage("Saved request · auth tokens, passwords and sensitive named fields omitted")

    def delete_saved(self):
        item = self.saved_list.currentItem()
        if not item:
            return
        index = item.data(Qt.ItemDataRole.UserRole)
        if 0 <= index < len(self.saved):
            if QMessageBox.question(self, "Remove saved request", f"Remove '{self.saved[index].get('name', 'request')}'?") != QMessageBox.StandardButton.Yes:
                return
            del self.saved[index]
            self._write_saved()
            self._refresh_sidebar()

    def _refresh_sidebar(self):
        self.saved_list.clear()
        for index, saved in enumerate(self.saved):
            item = QListWidgetItem("★  " + saved.get("name", "Unnamed"))
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.saved_list.addItem(item)
        self.history_list.clear()
        for index, spec in enumerate(self.history):
            clean_url = spec.url.split("?")[0]
            item = QListWidgetItem(f"{spec.method}   {clean_url[:51]}")
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.history_list.addItem(item)

    def load_sidebar_item(self, item: QListWidgetItem):
        index = item.data(Qt.ItemDataRole.UserRole)
        try:
            if self.sender() is self.saved_list:
                spec = RequestSpec.from_dict(self.saved[index]["request"])
            else:
                spec = copy.deepcopy(self.history[index])
            self.load_spec(spec)
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            QMessageBox.warning(self, "Cannot load request", str(exc))

    def export_request(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export current request", "request.volt.json", "Volt requests (*.json)")
        if not path:
            return
        try:
            payload = {"format": "volt-http/1", "request": self.current_spec().export(redact=True)}
            Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self.statusBar().showMessage("Exported · auth secrets omitted, review URL and body for credentials")

    def import_request(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import request", "", "Volt requests (*.json)")
        if not path:
            return
        try:
            if Path(path).stat().st_size > 1024 * 1024:
                raise ValueError("Request JSON file must be under 1 MiB")
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            spec = RequestSpec.from_dict(data.get("request", data))
            self.load_spec(spec)
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            QMessageBox.warning(self, "Import failed", str(exc))

    def closeEvent(self, event):
        if self.active_worker:
            self.active_worker.cancel_event.set()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("FLukeQuery")
    app.setOrganizationName("FLukeQuery")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = FLukeQueryWindow()
    window.show()
    return app.exec()
