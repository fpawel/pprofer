import datetime

import pyqtgraph as pg


class TimeAxis(pg.AxisItem):
    """Ось X, которая показывает unix timestamp как обычное время HH:MM:SS."""

    def tickStrings(self, values, scale, spacing):
        """Преобразует набор значений оси в набор строк-подписей."""
        labels = []
        for v in values:
            try:
                dt = datetime.datetime.fromtimestamp(v)
                labels.append(dt.strftime("%H:%M:%S"))
            except Exception:
                # Если значение не удалось превратить в timestamp,
                # лучше показать пустую подпись, чем уронить отрисовку оси.
                labels.append("")
        return labels
