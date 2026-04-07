import time

from PyQt5 import QtCore, QtGui, QtWidgets

from .plot_widget import PlotWidget
from .sse import SseClient
from .stack_client import get_stack

PROFILES = [
    "heap",
    "goroutine",
    "allocs",
    "profile",
    "block",
    "mutex",
    "threadcreate",
]

PROFILE_MODE = {
    "heap": "bytes",
    "allocs": "bytes",
    "goroutine": "count",
    "threadcreate": "count",
    "profile": "duration_ns",
    "block": "duration_ns",
    "mutex": "duration_ns",
}

LOG_SCALE_PROFILES = {"heap", "allocs", "profile", "block", "mutex"}


def format_stack_frames(frames):
    if not frames:
        return "Стектрейс недоступен."

    lines = []
    for index, frame in enumerate(frames, 1):
        func = frame.get("function") or "<unknown>"
        file = frame.get("file") or ""
        line = frame.get("line")

        lines.append(f"{index:>2}. {func}")
        if file:
            if line:
                lines.append(f"    {file}:{line}")
            else:
                lines.append(f"    {file}")

    return "\n".join(lines)


class StackFetchThread(QtCore.QThread):
    loaded = QtCore.pyqtSignal(int, object)
    failed = QtCore.pyqtSignal(int, str)

    def __init__(self, base_url, func, line, inline, request_id, parent=None):
        super().__init__(parent)
        self.base_url = base_url
        self.func = func
        self.line = line
        self.inline = inline
        self.request_id = request_id

    def run(self):
        try:
            frames = get_stack(
                base_url=self.base_url,
                func=self.func,
                line=self.line,
                inline=self.inline,
            )
        except Exception as exc:
            self.failed.emit(self.request_id, str(exc))
            return

        self.loaded.emit(self.request_id, frames)


class SeriesListWidget(QtWidgets.QWidget):
    series_selected = QtCore.pyqtSignal(str)

    def __init__(self, plot_widget, parent=None):
        super().__init__(parent)
        self.plot_widget = plot_widget
        self._selected_key = None
        self._items_by_key = {}

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(8)

        title = QtWidgets.QLabel("Series")
        title.setStyleSheet("font-weight: bold;")
        root_layout.addWidget(title)

        buttons_layout = QtWidgets.QHBoxLayout()
        self.select_all_button = QtWidgets.QPushButton("Show all")
        self.hide_all_button = QtWidgets.QPushButton("Hide all")
        buttons_layout.addWidget(self.select_all_button)
        buttons_layout.addWidget(self.hide_all_button)
        root_layout.addLayout(buttons_layout)

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.list_widget.setUniformItemSizes(True)
        root_layout.addWidget(self.list_widget, 1)

        self.select_all_button.clicked.connect(self.show_all)
        self.hide_all_button.clicked.connect(self.hide_all)
        self.list_widget.currentItemChanged.connect(self._on_current_item_changed)
        self.list_widget.itemChanged.connect(self._on_item_changed)

    def current_key(self):
        return self._selected_key

    def _on_current_item_changed(self, current, _previous):
        if current is None:
            self._selected_key = None
            self.series_selected.emit("")
            return

        key = current.data(QtCore.Qt.UserRole)
        self._selected_key = key
        self.list_widget.scrollToItem(current, QtWidgets.QAbstractItemView.EnsureVisible)
        self.series_selected.emit(key)

    def _on_item_changed(self, item):
        key = item.data(QtCore.Qt.UserRole)
        visible = item.checkState() == QtCore.Qt.Checked
        self.plot_widget.set_series_visible(key, visible)

    def refresh_visible_series(self):
        if self.plot_widget.show_all_series:
            keys = list(self.plot_widget.data.keys())
        else:
            keys = list(self.plot_widget.visible_series_keys())

        if self._selected_key and self._selected_key in self.plot_widget.data and self._selected_key not in keys:
            keys.append(self._selected_key)

        keys.sort(key=lambda k: self.plot_widget.series_score(k), reverse=True)

        final_key = self._selected_key
        if final_key not in keys:
            final_key = keys[0] if keys else None

        self._items_by_key = {}

        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        for key in keys:
            name = self.plot_widget.series_names.get(key, key)
            color = self.plot_widget.color_for_key(key)

            item = QtWidgets.QListWidgetItem(name)
            item.setData(QtCore.Qt.UserRole, key)
            item.setFlags(
                QtCore.Qt.ItemIsEnabled
                | QtCore.Qt.ItemIsSelectable
                | QtCore.Qt.ItemIsUserCheckable
            )
            item.setCheckState(
                QtCore.Qt.Checked
                if self.plot_widget.series_visible.get(key, True)
                else QtCore.Qt.Unchecked
            )
            item.setForeground(QtGui.QColor(color))

            self.list_widget.addItem(item)
            self._items_by_key[key] = item

        if final_key is not None and final_key in self._items_by_key:
            self.list_widget.setCurrentItem(self._items_by_key[final_key])
            self.list_widget.scrollToItem(
                self._items_by_key[final_key],
                QtWidgets.QAbstractItemView.EnsureVisible,
            )

        self.list_widget.blockSignals(False)

        if final_key != self._selected_key:
            self._selected_key = final_key
            self.series_selected.emit(final_key or "")

    def show_all(self):
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setCheckState(QtCore.Qt.Checked)
            key = item.data(QtCore.Qt.UserRole)
            self.plot_widget.set_series_visible(key, True)
        self.list_widget.blockSignals(False)

    def hide_all(self):
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setCheckState(QtCore.Qt.Unchecked)
            key = item.data(QtCore.Qt.UserRole)
            self.plot_widget.set_series_visible(key, False)
        self.list_widget.blockSignals(False)


class ProfileTab(QtWidgets.QWidget):
    def __init__(self, base_url, profile_name, mode, max_visible_series=10, view_seconds=300, parent=None):
        super().__init__(parent)

        self.base_url = base_url
        self.profile_name = profile_name
        self._stack_request_id = 0

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        controls_layout = QtWidgets.QHBoxLayout()

        self.follow_live_checkbox = QtWidgets.QCheckBox("Follow live")
        self.follow_live_checkbox.setChecked(True)
        controls_layout.addWidget(self.follow_live_checkbox)

        self.view_all_button = QtWidgets.QPushButton("View all")
        controls_layout.addWidget(self.view_all_button)

        self.top_n_button = QtWidgets.QPushButton("Top 10")
        controls_layout.addWidget(self.top_n_button)

        self.sort_combo = QtWidgets.QComboBox()
        self.sort_combo.addItems(["last", "avg", "max"])
        controls_layout.addWidget(self.sort_combo)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        outer_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        layout.addWidget(outer_splitter)

        self.plot = PlotWidget(
            profile_name,
            mode=mode,
            max_visible_series=max_visible_series,
            view_seconds=view_seconds,
            log_y=profile_name in LOG_SCALE_PROFILES,
        )
        outer_splitter.addWidget(self.plot)

        right_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        outer_splitter.addWidget(right_splitter)

        self.series_list = SeriesListWidget(self.plot)
        self.series_list.setMinimumWidth(360)
        right_splitter.addWidget(self.series_list)

        stack_panel = QtWidgets.QWidget()
        stack_layout = QtWidgets.QVBoxLayout(stack_panel)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.setSpacing(6)

        stack_title = QtWidgets.QLabel("Stack trace")
        stack_title.setStyleSheet("font-weight: bold;")
        stack_layout.addWidget(stack_title)

        self.stack_series_label = QtWidgets.QLabel("Серия не выбрана")
        self.stack_series_label.setWordWrap(True)
        stack_layout.addWidget(self.stack_series_label)

        self.stack_view = QtWidgets.QPlainTextEdit()
        self.stack_view.setReadOnly(True)
        self.stack_view.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.stack_view.setStyleSheet(
            "font-family: Consolas, 'Courier New', monospace; font-size: 12px;"
        )
        self.stack_view.setPlainText("Выбери серию справа, чтобы увидеть стектрейс.")
        stack_layout.addWidget(self.stack_view, 1)

        right_splitter.addWidget(stack_panel)

        outer_splitter.setStretchFactor(0, 1)
        outer_splitter.setStretchFactor(1, 0)
        outer_splitter.setSizes([1100, 420])

        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 1)
        right_splitter.setSizes([420, 320])

        self.follow_live_checkbox.toggled.connect(self.plot.set_follow_live)
        self.view_all_button.clicked.connect(self.plot.view_all)
        self.top_n_button.clicked.connect(self.on_show_top_n)
        self.sort_combo.currentTextChanged.connect(self.on_sort_changed)
        self.plot.manual_view_activated.connect(self._on_manual_view_activated)
        self.series_list.series_selected.connect(self.on_series_selected)

    def _on_manual_view_activated(self):
        self.follow_live_checkbox.blockSignals(True)
        self.follow_live_checkbox.setChecked(False)
        self.follow_live_checkbox.blockSignals(False)

    def on_show_top_n(self):
        self.plot.show_top_n()

    def on_sort_changed(self, mode):
        self.plot.sort_mode = mode

    def on_series_selected(self, key):
        self.plot.set_selected_series(key)

        if not key:
            self.stack_series_label.setText("Серия не выбрана")
            self.stack_view.setPlainText("Выбери серию справа, чтобы увидеть стектрейс.")
            return

        meta = self.plot.series_meta.get(key) or {}
        func = meta.get("func", "")
        line = meta.get("line", "")
        inline = meta.get("inline", "")

        title = func or key
        if line:
            title = f"{title}\n{line}"
        if inline:
            title = f"{title}\n{inline}"

        self.stack_series_label.setText(title)
        self.stack_view.setPlainText("Загрузка стектрейса...")

        self._stack_request_id += 1
        request_id = self._stack_request_id

        thread = StackFetchThread(
            base_url=self.base_url,
            func=func,
            line=line,
            inline=inline,
            request_id=request_id,
            parent=self,
        )
        thread.loaded.connect(self._on_stack_loaded)
        thread.failed.connect(self._on_stack_failed)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _on_stack_loaded(self, request_id, frames):
        if request_id != self._stack_request_id:
            return
        self.stack_view.setPlainText(format_stack_frames(frames))

    def _on_stack_failed(self, request_id, error_text):
        if request_id != self._stack_request_id:
            return
        self.stack_view.setPlainText(f"Не удалось загрузить стектрейс.\n\n{error_text}")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, base_url):
        super().__init__()

        self.base_url = base_url
        self.setWindowTitle("pprof viewer")
        self.resize(1600, 1000)

        root = QtWidgets.QWidget()
        self.setCentralWidget(root)

        root_layout = QtWidgets.QVBoxLayout(root)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)

        self.tabs = QtWidgets.QTabWidget()
        root_layout.addWidget(self.tabs)

        self.plots = {}

        max_visible_by_profile = {
            "heap": 10,
            "goroutine": 10,
            "allocs": 10,
            "profile": 10,
            "block": 10,
            "mutex": 10,
            "threadcreate": 10,
        }

        view_seconds_by_profile = {
            "heap": 300,
            "goroutine": 300,
            "allocs": 300,
            "profile": 300,
            "block": 300,
            "mutex": 300,
            "threadcreate": 300,
        }

        for profile in PROFILES:
            tab = ProfileTab(
                base_url=base_url,
                profile_name=profile,
                mode=PROFILE_MODE[profile],
                max_visible_series=max_visible_by_profile[profile],
                view_seconds=view_seconds_by_profile[profile],
            )
            self.tabs.addTab(tab, profile)
            self.plots[profile] = tab.plot

        self.client = SseClient(base_url, PROFILES)
        self.client.event.connect(self.on_event)
        self.client.start()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)

    def on_event(self, ev):
        plot = self.plots.get(ev["_type"])
        if plot is None:
            return

        key = f"{ev['func']}|{ev['line']}|{ev.get('inline', '')}"

        display_name = f"{ev['func']} — {ev['line']}"
        if ev.get("inline"):
            display_name += " (inl)"

        plot.add_point(
            key=key,
            ts=ev["_ts"],
            value=ev["flat"],
            display_name=display_name,
            meta={
                "func": ev["func"],
                "line": ev["line"],
                "inline": ev.get("inline", ""),
                "profile": ev["_type"],
            },
        )

    def refresh(self):
        now = time.time()
        for tab_index in range(self.tabs.count()):
            tab = self.tabs.widget(tab_index)
            tab.plot.refresh(now)
            tab.series_list.refresh_visible_series()

    def closeEvent(self, event):
        self.client.stop()
        self.client.wait(2000)
        super().closeEvent(event)