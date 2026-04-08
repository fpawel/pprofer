import math
from collections import defaultdict

import pyqtgraph as pg
from PyQt5 import QtCore

from ui.human_axis import HumanAxis
from ui.time_axis import TimeAxis

# Небольшая фиксированная палитра для серий.
# Цвет закрепляется за key и потом переиспользуется.
SERIES_COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]


class PlotWidget(pg.PlotWidget):
    """
    График, который хранит live-данные по сериям и управляет их отображением.

    Внутри есть три важных слоя:
    1. self.data            — все накопленные точки по ключу серии
    2. self.active_keys     — какие серии сейчас вообще присутствуют на графике
    3. self.series_visible  — какие серии пользователь явно скрыл/показал
    """

    series_added = QtCore.pyqtSignal(str)
    series_removed = QtCore.pyqtSignal(str)
    manual_view_activated = QtCore.pyqtSignal()

    def __init__(
        self,
        title,
        mode="bytes",
        max_visible_series=10,
        view_seconds=300,
        log_y=False,
    ):
        """
        Создаёт график с кастомными осями.

        mode влияет только на формат подписей оси Y.
        log_y переводит Y в логарифмический режим.
        """
        axis = {
            "left": HumanAxis(orientation="left", mode=mode, log_scale=log_y),
            "bottom": TimeAxis(orientation="bottom"),
        }
        super().__init__(axisItems=axis)

        self.max_visible_series = max_visible_series
        self.view_seconds = view_seconds
        self.min_x_padding_seconds = 1.0

        # follow_live=True  -> X-окно автоматически едет вправо за новыми данными
        # show_all_series=True -> на графике рисуем вообще все известные серии
        self.follow_live = True
        self.show_all_series = False
        self.sort_mode = "last"
        self.log_y = log_y

        # Когда мы сами меняем диапазон X/Y программно,
        # не хотим воспринимать это как ручное действие пользователя.
        self._ignore_manual_range_signal = False

        self.setBackground("w")
        self.setMinimumHeight(420)
        self.showGrid(x=True, y=True, alpha=0.2)
        self.setTitle(title, color="k", size="14pt")

        if self.log_y:
            self.setLogMode(y=True)

        # Делаем оси контрастными на белом фоне.
        left_axis = self.getAxis("left")
        bottom_axis = self.getAxis("bottom")
        left_axis.setTextPen(pg.mkPen("k"))
        bottom_axis.setTextPen(pg.mkPen("k"))
        left_axis.setPen(pg.mkPen("k"))
        bottom_axis.setPen(pg.mkPen("k"))

        # data[key] = [(timestamp, value), ...]
        self.data = defaultdict(list)

        # Небольшие агрегаты, чтобы быстро ранжировать серии,
        # не пересчитывая всё заново по всем точкам.
        self.series_stats = {}

        # curves[key] = объект линии на графике
        self.curves = {}

        # Здесь хранится всё, что связано с отображением и выбором.
        self.series_colors = {}
        self.series_visible = {}
        self.series_names = {}
        self.series_meta = {}
        self.active_keys = set()
        self.selected_key = None

        vb = self.getViewBox()
        vb.sigRangeChangedManually.connect(self._on_manual_range_changed)

    def _on_manual_range_changed(self, *args):
        """
        Вызывается, когда пользователь руками двигает/зумит график.

        После такого действия отключаем follow_live, чтобы UI
        не "боролся" с пользователем и не возвращал график назад.
        """
        if self._ignore_manual_range_signal:
            return
        if self.follow_live:
            self.follow_live = False
            self.manual_view_activated.emit()

    def set_follow_live(self, enabled: bool):
        """Включает/выключает автопрокрутку по оси X за новыми данными."""
        self.follow_live = enabled
        if enabled:
            # При возвращении в live-режим снова показываем top N,
            # а не "все серии", иначе график быстро захламится.
            self.show_all_series = False
            self.update_x_range()

    def set_show_all_series(self, enabled: bool):
        """Переключает режим отображения всех известных серий."""
        self.show_all_series = enabled

    def show_top_n(self):
        """Отключает live-follow и оставляет режим показа только top N серий."""
        self.follow_live = False
        self.show_all_series = False
        self.manual_view_activated.emit()

    def set_selected_series(self, key):
        """Запоминает выбранную серию и визуально выделяет её более толстой линией."""
        self.selected_key = key or None
        for series_key in self.curves.keys():
            self._update_curve_style(series_key)

    def color_for_key(self, key):
        """
        Возвращает цвет серии.

        Цвет назначается один раз при первом появлении key и дальше остаётся тем же.
        """
        if key not in self.series_colors:
            idx = len(self.series_colors) % len(SERIES_COLORS)
            self.series_colors[key] = SERIES_COLORS[idx]
        return self.series_colors[key]

    def add_point(self, key, ts, value, display_name=None, meta=None):
        """
        Добавляет новую точку в серию.

        key — внутренний идентификатор серии.
        display_name — подпись для списка/легенды.
        meta — всё, что потом пригодится при запросе stack trace.
        """
        self.data[key].append((ts, value))

        stats = self.series_stats.get(key)
        if stats is None:
            self.series_stats[key] = {
                "last": value,
                "sum": value,
                "count": 1,
                "max": value,
            }
        else:
            stats["last"] = value
            stats["sum"] += value
            stats["count"] += 1
            if value > stats["max"]:
                stats["max"] = value

        if key not in self.series_visible:
            # Новую серию по умолчанию показываем.
            self.series_visible[key] = True
        if display_name:
            self.series_names[key] = display_name
        if meta is not None:
            self.series_meta[key] = meta

    def set_series_visible(self, key, visible):
        """Показывает или скрывает конкретную серию."""
        self.series_visible[key] = visible
        curve = self.curves.get(key)
        if curve is not None:
            curve.setVisible(visible)
        if self.follow_live:
            self.update_x_range()

    def series_score(self, key):
        """
        Считает "вес" серии для сортировки.

        last — по последнему значению
        avg  — по среднему
        max  — по максимуму
        """
        stats = self.series_stats.get(key)
        if not stats or stats["count"] == 0:
            return 0

        if self.sort_mode == "last":
            return stats["last"]

        if self.sort_mode == "avg":
            return stats["sum"] / stats["count"]

        if self.sort_mode == "max":
            return stats["max"]

        return stats["last"]

    def top_series_keys(self):
        """Возвращает ключи top N серий по текущему правилу сортировки."""
        ranked = []
        for key, points in self.data.items():
            if not points:
                continue
            ranked.append((self.series_score(key), key))
        ranked.sort(reverse=True, key=lambda x: x[0])
        return [key for _, key in ranked[: self.max_visible_series]]

    def visible_series_keys(self):
        """
        Возвращает активные серии в порядке убывания их веса.

        Это используется, например, правой панелью со списком серий.
        """
        return sorted(self.active_keys, key=lambda k: self.series_score(k), reverse=True)

    def _create_curve(self, key):
        """Создаёт объект линии pyqtgraph для серии, если её ещё нет на графике."""
        color = self.color_for_key(key)
        pen = pg.mkPen(color=color, width=2)
        name = self.series_names.get(key, key)

        curve = self.plot(
            name=name,
            pen=pen,
            symbol="o",
            symbolSize=5,
            symbolBrush=color,
            symbolPen=color,
        )
        self.curves[key] = curve
        self._update_curve_style(key)

    def _remove_curve(self, key):
        """Удаляет линию серии с графика, но не удаляет исторические данные."""
        curve = self.curves.pop(key, None)
        if curve is not None:
            self.removeItem(curve)

    def _update_curve_style(self, key):
        """Обновляет визуальный стиль линии, например толщину выбранной серии."""
        curve = self.curves.get(key)
        if curve is None:
            return

        color = self.color_for_key(key)
        is_selected = key == self.selected_key
        width = 4 if is_selected else 2

        curve.setPen(pg.mkPen(color=color, width=width))
        curve.setZValue(10 if is_selected else 0)

    def _visible_points_bounds(self):
        """
        Ищет минимальный и максимальный X среди активных и видимых серий.

        Эти значения нужны, чтобы корректно двигать live-окно по оси времени.
        """
        min_x = None
        max_x = None

        for key in self.active_keys:
            if not self.series_visible.get(key, True):
                continue

            points = self.data.get(key)
            if not points:
                continue

            first_x = points[0][0]
            last_x = points[-1][0]

            if min_x is None or first_x < min_x:
                min_x = first_x
            if max_x is None or last_x > max_x:
                max_x = last_x

        return min_x, max_x

    def update_x_range(self):
        """
        Подстраивает окно просмотра по X, если включён follow_live.

        Логика такая:
        - если данных мало, показываем их все с небольшим отступом;
        - если данных уже много, держим справа последние view_seconds секунд.
        """
        if not self.follow_live:
            return

        min_x, max_x = self._visible_points_bounds()
        if min_x is None or max_x is None:
            return

        self._ignore_manual_range_signal = True
        try:
            if max_x <= min_x:
                # Когда есть одна точка или все точки на одном timestamp,
                # иначе диапазон будет нулевой и график "схлопнется".
                left = min_x - self.min_x_padding_seconds
                right = max_x + self.min_x_padding_seconds
                self.setXRange(left, right, padding=0)
                return

            span = max_x - min_x

            if span < self.view_seconds:
                padding = max(span * 0.05, self.min_x_padding_seconds)
                left = min_x - padding
                right = max_x + padding
            else:
                left = max_x - self.view_seconds
                right = max_x

            self.setXRange(left, right, padding=0)
        finally:
            self._ignore_manual_range_signal = False

    def view_all(self):
        """
        Показывает все известные серии и весь накопленный диапазон X/Y.

        В этом режиме follow_live выключен: пользователь явно попросил
        обзор всей истории, а не "живое окно справа".
        """
        self.follow_live = False
        self.show_all_series = True
        self.manual_view_activated.emit()

        min_x = None
        max_x = None
        min_y = None
        max_y = None

        all_keys = list(self.data.keys())

        for key in all_keys:
            if key not in self.curves:
                self._create_curve(key)
                self.series_added.emit(key)

        self.active_keys = set(all_keys)

        for key in self.active_keys:
            if not self.series_visible.get(key, True):
                continue

            points = self.data.get(key)
            if not points:
                continue

            xs = [t for t, _ in points]
            ys = [max(v, 1) if self.log_y else v for _, v in points]

            x1, x2 = min(xs), max(xs)
            y1, y2 = min(ys), max(ys)

            min_x = x1 if min_x is None else min(min_x, x1)
            max_x = x2 if max_x is None else max(max_x, x2)
            min_y = y1 if min_y is None else min(min_y, y1)
            max_y = y2 if max_y is None else max(max_y, y2)

        if min_x is None or max_x is None or min_y is None or max_y is None:
            return

        if min_x == max_x:
            min_x -= self.min_x_padding_seconds
            max_x += self.min_x_padding_seconds

        self._ignore_manual_range_signal = True
        try:
            self.setXRange(min_x, max_x, padding=0.02)

            if self.log_y:
                # Для логарифмической шкалы значения должны быть > 0.
                min_y = max(min_y, 1)
                max_y = max(max_y, min_y * 1.01)

                log_min_y = math.log10(min_y)
                log_max_y = math.log10(max_y)

                if log_min_y == log_max_y:
                    log_min_y -= 0.1
                    log_max_y += 0.1

                self.setYRange(log_min_y, log_max_y, padding=0.05)
            else:
                if min_y == max_y:
                    delta = max(abs(min_y) * 0.05, 1.0)
                    min_y -= delta
                    max_y += delta

                self.setYRange(min_y, max_y, padding=0.05)
        finally:
            self._ignore_manual_range_signal = False

    def refresh(self, _now):
        """
        Главный метод перерисовки графика.

        На каждом тике:
        1. выбираем, какие серии должны быть активны сейчас;
        2. создаём/удаляем линии;
        3. обновляем данные кривых;
        4. подстраиваем диапазоны осей.
        """
        if self.show_all_series:
            new_active_keys = set(self.data.keys())
        else:
            new_active_keys = set(self.top_series_keys())

        # Выбранную пользователем серию не выбрасываем из графика,
        # даже если она уже не входит в текущий top N.
        if self.selected_key and self.selected_key in self.data:
            new_active_keys.add(self.selected_key)

        removed_keys = self.active_keys - new_active_keys
        for key in removed_keys:
            self._remove_curve(key)
            self.series_removed.emit(key)

        added_keys = new_active_keys - self.active_keys
        for key in added_keys:
            self._create_curve(key)
            self.series_added.emit(key)

        self.active_keys = new_active_keys

        for key in sorted(self.active_keys, key=lambda k: self.series_score(k), reverse=True):
            points = self.data.get(key)
            curve = self.curves.get(key)
            if not points or curve is None:
                continue

            xs = [t for t, _ in points]
            ys = [max(v, 1) if self.log_y else v for _, v in points]

            curve.setData(xs, ys)

            visible = self.series_visible.get(key, True)
            curve.setVisible(visible)
            self._update_curve_style(key)

        self.update_x_range()
        if self.follow_live:
            # Y-ось в live-режиме удобно автоподстраивать,
            # иначе новые пики могут уезжать за границы.
            self.getViewBox().enableAutoRange(axis="y")
