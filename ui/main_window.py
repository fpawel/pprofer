import time

from PyQt5 import QtCore, QtWidgets

from .plot_widget import PlotWidget
from .sse import SseClient

PROFILES = [
    "heap",
    "goroutine",
    "allocs",
    "profile",
    "block",
    "mutex",
    "threadcreate",
]

BYTES_PROFILES = {"heap", "allocs"}


class SeriesLegendWidget(QtWidgets.QWidget):
    def __init__(self, plot_widget, parent=None):
        super().__init__(parent)
        self.plot_widget = plot_widget
        self.checkboxes = {}

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

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        root_layout.addWidget(self.scroll, 1)

        self.content = QtWidgets.QWidget()
        self.scroll.setWidget(self.content)

        self.content_layout = QtWidgets.QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(4, 4, 4, 4)
        self.content_layout.setSpacing(4)
        self.content_layout.addStretch()

        self.select_all_button.clicked.connect(self.show_all)
        self.hide_all_button.clicked.connect(self.hide_all)

        self.plot_widget.series_added.connect(self.ensure_series)
        self.plot_widget.series_removed.connect(self.remove_series)

    def ensure_series(self, key):
        if key in self.checkboxes:
            return

        checkbox = QtWidgets.QCheckBox(key)
        checkbox.setChecked(self.plot_widget.series_visible.get(key, True))
        checkbox.toggled.connect(
            lambda checked, series_key=key: self.plot_widget.set_series_visible(series_key, checked)
        )

        self.checkboxes[key] = checkbox
        self.content_layout.insertWidget(self.content_layout.count() - 1, checkbox)

    def remove_series(self, key):
        checkbox = self.checkboxes.pop(key, None)
        if checkbox is None:
            return
        checkbox.setParent(None)
        checkbox.deleteLater()

    def refresh_visible_series(self):
        allowed = set(self.plot_widget.visible_series_keys())
        for key, checkbox in self.checkboxes.items():
            checkbox.setVisible(key in allowed)

    def show_all(self):
        for key, checkbox in self.checkboxes.items():
            if not checkbox.isVisible():
                continue
            checkbox.blockSignals(True)
            checkbox.setChecked(True)
            checkbox.blockSignals(False)
            self.plot_widget.set_series_visible(key, True)

    def hide_all(self):
        for key, checkbox in self.checkboxes.items():
            if not checkbox.isVisible():
                continue
            checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(False)
            self.plot_widget.set_series_visible(key, False)


class ProfileTab(QtWidgets.QWidget):
    def __init__(self, profile_name, mode, max_visible_series=10, view_seconds=300, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        controls_layout = QtWidgets.QHBoxLayout()

        self.follow_live_checkbox = QtWidgets.QCheckBox("Follow live")
        self.follow_live_checkbox.setChecked(True)
        controls_layout.addWidget(self.follow_live_checkbox)

        self.view_all_button = QtWidgets.QPushButton("View all")
        controls_layout.addWidget(self.view_all_button)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        layout.addWidget(splitter)

        self.plot = PlotWidget(
            profile_name,
            mode=mode,
            max_visible_series=max_visible_series,
            view_seconds=view_seconds,
        )
        splitter.addWidget(self.plot)

        self.legend = SeriesLegendWidget(self.plot)
        self.legend.setMinimumWidth(320)
        splitter.addWidget(self.legend)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([1100, 320])

        self.follow_live_checkbox.toggled.connect(self.plot.set_follow_live)
        self.view_all_button.clicked.connect(self.plot.view_all)
        self.plot.manual_view_activated.connect(self._on_manual_view_activated)

    def _on_manual_view_activated(self):
        self.follow_live_checkbox.blockSignals(True)
        self.follow_live_checkbox.setChecked(False)
        self.follow_live_checkbox.blockSignals(False)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, base_url):
        super().__init__()

        self.base_url = base_url
        self.setWindowTitle("pprof viewer")
        self.resize(1400, 1000)

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
            mode = "bytes" if profile in BYTES_PROFILES else "count"

            tab = ProfileTab(
                profile_name=profile,
                mode=mode,
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
        key = f"{ev['line']}|{ev.get('inline', '')}"
        plot = self.plots.get(ev["_type"])
        if plot is not None:
            plot.add_point(key, ev["_ts"], ev["flat"])

    def refresh(self):
        now = time.time()
        for tab_index in range(self.tabs.count()):
            tab = self.tabs.widget(tab_index)
            tab.plot.refresh(now)
            tab.legend.refresh_visible_series()

    def closeEvent(self, event):
        self.client.stop()
        self.client.wait(2000)
        super().closeEvent(event)