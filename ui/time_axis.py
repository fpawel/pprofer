import datetime

import pyqtgraph as pg


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
