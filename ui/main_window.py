import time

from PyQt5 import QtCore, QtWidgets

from .labels_fetch_thread import LabelsFetchThread
from .profile_tab import ProfileTab
from .sse import SseClient

# Набор профилей, которые UI показывает отдельными вкладками.
PROFILES = [
    "heap",
    "goroutine",
    "allocs",
    "profile",
    "block",
    "mutex",
    "threadcreate",
]

# Для каждого профиля выбираем способ форматирования оси Y.
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
    """
    Главное окно приложения.

    Его роль:
    - создать вкладки по профилям,
    - принять live-события из SSE,
    - разложить точки по нужным графикам,
    - периодически инициировать refresh UI,
    - один раз подтянуть labels.
    """

    def __init__(self, base_url):
        """Создаёт всё дерево виджетов и запускает фоновые механизмы UI."""
        super().__init__()

        self.base_url = base_url
        self._is_closing = False

        self.setWindowTitle("pprof viewer")
        self.resize(1600, 1000)

        root = QtWidgets.QWidget()
        self.setCentralWidget(root)

        root_layout = QtWidgets.QVBoxLayout(root)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)

        self.tabs = QtWidgets.QTabWidget()
        root_layout.addWidget(self.tabs)

        # Быстрый доступ к plot/tab по имени профиля.
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

        # SSE-клиент поставляет live-данные по всем профилям.
        self.client = SseClient(base_url, PROFILES)
        self.client.event.connect(self.on_event)
        self.client.start()

        # Таймер обновляет отрисовку графиков и правых списков.
        # Данные в графики добавляются сразу по событию, а redraw делаем пачкой раз в секунду.
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)

        # Labels обычно приходят один раз и потом почти не меняются.
        # Поэтому периодически спрашиваем backend, пока не получим непустой ответ.
        self.labels_thread = None
        self.labels_timer = QtCore.QTimer(self)
        self.labels_timer.timeout.connect(self.fetch_labels)
        self.labels_timer.start(1000)
        self.fetch_labels()

    def on_event(self, ev):
        """
        Принимает одно SSE-событие и добавляет точку на соответствующий график.

        ev приходит уже распарсенным словарём с полями от backend.
        """
        if self._is_closing:
            return

        plot = self.plots.get(ev["_type"])
        if plot is None:
            return

        # key должен однозначно описывать серию.
        # Здесь серия определяется функцией, строкой и inline-меткой.
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
        """
        Обновляет все вкладки.

        now сейчас не используется внутри PlotWidget, но сигнатура оставлена удобной:
        если позже понадобится age-based pruning, время уже будет под рукой.
        """
        if self._is_closing:
            return

        now = time.time()
        for tab_index in range(self.tabs.count()):
            tab = self.tabs.widget(tab_index)
            tab.plot.refresh(now)
            tab.series_list.refresh_visible_series()

    def _stop_labels_thread(self, wait_ms=2000):
        """Останавливает текущий labels-thread и ждёт его завершения."""
        thread = self.labels_thread
        self.labels_thread = None

        if thread is None:
            return

        thread.stop()
        thread.wait(wait_ms)

    def closeEvent(self, event):
        """
        Корректно останавливает фоновые механизмы перед закрытием окна.

        Порядок важен:
        1. перестаём запускать новые действия по таймерам;
        2. останавливаем сетевые worker-ы;
        3. дожидаемся их завершения;
        4. только потом даём Qt уничтожать дерево виджетов.
        """
        self._is_closing = True

        self.timer.stop()
        self.labels_timer.stop()

        self.client.stop()
        self._stop_labels_thread()

        for tab in self.profile_tabs.values():
            tab.shutdown()

        self.client.wait(2000)
        super().closeEvent(event)

    def fetch_labels(self):
        """
        Запускает фоновую загрузку labels, если сейчас ещё нет активного запроса.
        """
        if self._is_closing:
            return

        if self.labels_thread is not None and self.labels_thread.isRunning():
            return

        self.labels_thread = LabelsFetchThread(self.base_url, self)
        self.labels_thread.loaded.connect(self.on_labels_loaded)
        self.labels_thread.failed.connect(self.on_labels_failed)
        self.labels_thread.finished.connect(self.on_labels_thread_finished)
        self.labels_thread.start()

    def on_labels_loaded(self, labels):
        """
        Применяет labels ко всем вкладкам.

        После первого успешного получения labels таймер можно выключить.
        """
        if self._is_closing:
            return

        if not labels:
            return

        for tab in self.profile_tabs.values():
            tab.set_labels(labels)

        self.labels_timer.stop()

    def on_labels_failed(self, _error):
        """
        Ошибку намеренно игнорируем.

        labels не критичны для основного сценария, поэтому просто дождёмся следующей попытки.
        """
        if self._is_closing:
            return

    def on_labels_thread_finished(self):
        """Сбрасывает ссылку на завершившийся labels-thread."""
        self.labels_thread = None
