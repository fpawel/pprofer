import time

from PyQt5 import QtCore, QtWidgets

from .profile_tab import ProfileTab
from .sse import SseClient
from .labels_fetch_thread import LabelsFetchThread

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
        self.profile_tabs = {}

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
            self.profile_tabs[profile] = tab

        self.client = SseClient(base_url, PROFILES)
        self.client.event.connect(self.on_event)
        self.client.start()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)

        self.labels_thread = None
        self.labels_timer = QtCore.QTimer(self)
        self.labels_timer.timeout.connect(self.fetch_labels)
        self.labels_timer.start(1000)
        self.fetch_labels()

    def on_event(self, ev):
        plot = self.plots.get(ev["_type"])
        if plot is None:
            return

        key = f"{ev['func']}|{ev['line']}|{ev.get('inline', '')}"

        display_name = ev["func"]
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

    def fetch_labels(self):
        if self.labels_thread is not None and self.labels_thread.isRunning():
            return

        self.labels_thread = LabelsFetchThread(self.base_url, self)
        self.labels_thread.loaded.connect(self.on_labels_loaded)
        self.labels_thread.failed.connect(self.on_labels_failed)
        self.labels_thread.finished.connect(self.on_labels_thread_finished)
        self.labels_thread.start()

    def on_labels_loaded(self, labels):
        if not labels:
            return

        for tab in self.profile_tabs.values():
            tab.set_labels(labels)

        self.labels_timer.stop()

    def on_labels_failed(self, _error):
        pass

    def on_labels_thread_finished(self):
        self.labels_thread = None