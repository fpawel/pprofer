import datetime
import math
from collections import defaultdict

import humanize
import pyqtgraph as pg
from PyQt5 import QtCore


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


class TimeAxis(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        labels = []
        for v in values:
            try:
                dt = datetime.datetime.fromtimestamp(v)
                labels.append(dt.strftime("%H:%M:%S"))
            except Exception:
                labels.append("")
        return labels


class HumanAxis(pg.AxisItem):
    def __init__(self, orientation, mode="bytes", log_scale=False):
        super().__init__(orientation=orientation)
        self.mode = mode
        self.log_scale = log_scale

    def tickStrings(self, values, scale, spacing):
        return [self.format_value(v) for v in values]

    def format_value(self, v):
        real_value = 10 ** v if self.log_scale else v

        if real_value <= 0:
            return "0"

        if self.mode == "bytes":
            return humanize.naturalsize(real_value, binary=True)

        if self.mode == "count":
            return str(int(real_value))

        if self.mode == "duration_ns":
            return self.format_duration_ns(real_value)

        return str(real_value)

    @staticmethod
    def format_duration_ns(ns):
        ns = float(ns)

        if ns >= 1_000_000_000:
            return f"{ns / 1_000_000_000:.2f} s"
        if ns >= 1_000_000:
            return f"{ns / 1_000_000:.2f} ms"
        if ns >= 1_000:
            return f"{ns / 1_000:.2f} µs"
        return f"{int(ns)} ns"


class PlotWidget(pg.PlotWidget):
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
        axis = {
            "left": HumanAxis(orientation="left", mode=mode, log_scale=log_y),
            "bottom": TimeAxis(orientation="bottom"),
        }
        super().__init__(axisItems=axis)

        self.max_visible_series = max_visible_series
        self.view_seconds = view_seconds
        self.min_x_padding_seconds = 1.0

        self.follow_live = True
        self.show_all_series = False
        self.log_y = log_y
        self._ignore_manual_range_signal = False

        self.setBackground("w")
        self.setMinimumHeight(420)
        self.showGrid(x=True, y=True, alpha=0.2)
        self.setTitle(title, color="k", size="14pt")

        if self.log_y:
            self.setLogMode(y=True)

        left_axis = self.getAxis("left")
        bottom_axis = self.getAxis("bottom")
        left_axis.setTextPen(pg.mkPen("k"))
        bottom_axis.setTextPen(pg.mkPen("k"))
        left_axis.setPen(pg.mkPen("k"))
        bottom_axis.setPen(pg.mkPen("k"))

        self.data = defaultdict(list)
        self.curves = {}
        self.series_colors = {}
        self.series_visible = {}
        self.series_names = {}
        self.active_keys = set()

        vb = self.getViewBox()
        vb.sigRangeChangedManually.connect(self._on_manual_range_changed)

    def _on_manual_range_changed(self, *args):
        if self._ignore_manual_range_signal:
            return
        if self.follow_live:
            self.follow_live = False
            self.manual_view_activated.emit()

    def set_follow_live(self, enabled: bool):
        self.follow_live = enabled
        if enabled:
            self.show_all_series = False
            self.update_x_range()

    def set_show_all_series(self, enabled: bool):
        self.show_all_series = enabled

    def show_top_n(self):
        self.follow_live = False
        self.show_all_series = False
        self.manual_view_activated.emit()

    def color_for_key(self, key):
        if key not in self.series_colors:
            idx = len(self.series_colors) % len(SERIES_COLORS)
            self.series_colors[key] = SERIES_COLORS[idx]
        return self.series_colors[key]

    def add_point(self, key, ts, value, display_name=None):
        self.data[key].append((ts, value))
        if key not in self.series_visible:
            self.series_visible[key] = True
        if display_name:
            self.series_names[key] = display_name

    def set_series_visible(self, key, visible):
        self.series_visible[key] = visible
        curve = self.curves.get(key)
        if curve is not None:
            curve.setVisible(visible)
        if self.follow_live:
            self.update_x_range()

    def top_series_keys(self):
        ranked = []
        for key, points in self.data.items():
            if not points:
                continue
            last_value = points[-1][1]
            ranked.append((last_value, key))
        ranked.sort(reverse=True, key=lambda x: x[0])
        return [key for _, key in ranked[: self.max_visible_series]]

    def visible_series_keys(self):
        return sorted(self.active_keys)

    def _create_curve(self, key):
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

    def _remove_curve(self, key):
        curve = self.curves.pop(key, None)
        if curve is not None:
            self.removeItem(curve)

    def _visible_points_bounds(self):
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
        if not self.follow_live:
            return

        min_x, max_x = self._visible_points_bounds()
        if min_x is None or max_x is None:
            return

        self._ignore_manual_range_signal = True
        try:
            if max_x <= min_x:
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
        if self.show_all_series:
            new_active_keys = set(self.data.keys())
        else:
            new_active_keys = set(self.top_series_keys())

        removed_keys = self.active_keys - new_active_keys
        for key in removed_keys:
            self._remove_curve(key)
            self.series_removed.emit(key)

        added_keys = new_active_keys - self.active_keys
        for key in added_keys:
            self._create_curve(key)
            self.series_added.emit(key)

        self.active_keys = new_active_keys

        for key in sorted(self.active_keys):
            points = self.data.get(key)
            curve = self.curves.get(key)
            if not points or curve is None:
                continue

            xs = [t for t, _ in points]
            ys = [max(v, 1) if self.log_y else v for _, v in points]

            curve.setData(xs, ys)

            visible = self.series_visible.get(key, True)
            curve.setVisible(visible)

        self.update_x_range()
        if self.follow_live:
            self.getViewBox().enableAutoRange(axis="y")