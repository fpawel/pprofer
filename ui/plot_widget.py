import datetime
from collections import defaultdict, deque

import humanize
import pyqtgraph as pg
from PyQt5 import QtCore, QtWidgets


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
    def __init__(self, orientation, mode="bytes"):
        super().__init__(orientation=orientation)
        self.mode = mode

    def tickStrings(self, values, scale, spacing):
        return [self.format_value(v) for v in values]

    def format_value(self, v):
        if self.mode == "bytes":
            return humanize.naturalsize(v, binary=True)
        if self.mode == "count":
            return str(int(v))
        return ""


class PlotWidget(pg.PlotWidget):
    series_added = QtCore.pyqtSignal(str)
    series_removed = QtCore.pyqtSignal(str)

    def __init__(self, title, mode="bytes", max_visible_series=10):
        axis = {
            "left": HumanAxis(orientation="left", mode=mode),
            "bottom": TimeAxis(orientation="bottom"),
        }
        super().__init__(axisItems=axis)

        self.max_visible_series = max_visible_series

        self.setBackground("w")
        self.setMinimumHeight(420)
        self.showGrid(x=True, y=True, alpha=0.2)
        self.setTitle(title, color="k", size="14pt")

        left_axis = self.getAxis("left")
        bottom_axis = self.getAxis("bottom")

        left_axis.setTextPen(pg.mkPen("k"))
        bottom_axis.setTextPen(pg.mkPen("k"))
        left_axis.setPen(pg.mkPen("k"))
        bottom_axis.setPen(pg.mkPen("k"))

        self.data = defaultdict(deque)
        self.curves = {}
        self.series_colors = {}
        self.series_visible = {}

    def visible_series_keys(self):
        return self.top_series_keys()

    def top_series_keys(self):
        ranked = []
        for key, dq in self.data.items():
            if not dq:
                continue
            ranked.append((dq[-1][1], key))  # последнее значение flat
        ranked.sort(reverse=True, key=lambda x: x[0])
        return [key for _, key in ranked[: self.max_visible_series]]

    def color_for_key(self, key):
        if key not in self.series_colors:
            idx = len(self.series_colors) % len(SERIES_COLORS)
            self.series_colors[key] = SERIES_COLORS[idx]
        return self.series_colors[key]

    def add_point(self, key, ts, value):
        dq = self.data[key]
        dq.append((ts, value))

        cutoff = ts - 60
        while dq and dq[0][0] < cutoff:
            dq.popleft()

        if key not in self.series_visible:
            self.series_visible[key] = True

    # def add_point(self, key, ts, value):
    #     is_new_series = key not in self.data
    #
    #     dq = self.data[key]
    #     dq.append((ts, value))
    #
    #     cutoff = ts - 60
    #     while dq and dq[0][0] < cutoff:
    #         dq.popleft()
    #
    #     if key not in self.curves:
    #         pen = pg.mkPen(color=self.color_for_key(key), width=2)
    #         curve = self.plot(
    #             name=key,
    #             pen=pen,
    #             symbol="o",
    #             symbolSize=6,
    #             symbolBrush=self.color_for_key(key),
    #             symbolPen=self.color_for_key(key),
    #         )
    #         self.curves[key] = curve
    #
    #     if key not in self.series_visible:
    #         self.series_visible[key] = True
    #
    #     self.curves[key].setVisible(self.series_visible[key])
    #
    #     if is_new_series:
    #         self.series_added.emit(key)

    def set_series_visible(self, key, visible):
        self.series_visible[key] = visible
        curve = self.curves.get(key)
        if curve is not None:
            curve.setVisible(visible)

    def all_series(self):
        return sorted(self.data.keys())

    def refresh(self, now):
        dead_keys = []

        for key, dq in self.data.items():
            while dq and dq[0][0] < now - 60:
                dq.popleft()

            if not dq:
                dead_keys.append(key)

        for key in dead_keys:
            curve = self.curves.pop(key, None)
            if curve is not None:
                self.removeItem(curve)
            self.data.pop(key, None)
            self.series_colors.pop(key, None)
            self.series_visible.pop(key, None)
            self.series_removed.emit(key)

        top_keys = self.top_series_keys()

        # удалить curves не из top N
        for key in list(self.curves.keys()):
            if key not in top_keys:
                curve = self.curves.pop(key)
                self.removeItem(curve)
                self.series_removed.emit(key)

        # создать curves только для top N
        for key in top_keys:
            if key not in self.curves:
                color = self.color_for_key(key)
                pen = pg.mkPen(color=color, width=2)
                curve = self.plot(
                    name=key,
                    pen=pen,
                    symbol="o",
                    symbolSize=5,
                    symbolBrush=color,
                    symbolPen=color,
                )
                self.curves[key] = curve
                self.series_added.emit(key)

        visible_keys = []

        for key in top_keys:
            dq = self.data.get(key)
            curve = self.curves.get(key)
            if not dq or curve is None:
                continue

            visible = self.series_visible.get(key, True)
            curve.setVisible(visible)

            if not visible:
                continue

            xs = [t for t, _ in dq]
            ys = [v for _, v in dq]
            curve.setData(xs, ys)
            visible_keys.append(key)

        if visible_keys:
            right = max(self.data[key][-1][0] for key in visible_keys if self.data[key])
            left = right - 60
            self.setXRange(left, right, padding=0)

        self.getViewBox().enableAutoRange(axis="y")