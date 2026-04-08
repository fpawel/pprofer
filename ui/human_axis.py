import humanize
import pyqtgraph as pg


class HumanAxis(pg.AxisItem):
    """
    Ось Y, которая форматирует значения в человекочитаемый вид.

    Примеры:
    - bytes      -> 12.3 MiB
    - count      -> 42
    - duration_ns -> 1.25 ms
    """

    def __init__(self, orientation, mode="bytes", log_scale=False):
        """Запоминает режим форматирования и используется ли логарифмическая шкала."""
        super().__init__(orientation=orientation)
        self.mode = mode
        self.log_scale = log_scale

    def tickStrings(self, values, scale, spacing):
        """QtGraph спрашивает подписи для tick-ов оси через этот метод."""
        return [self.format_value(v) for v in values]

    def format_value(self, v):
        """
        Преобразует числовое значение оси в строку.

        В log-scale сам pyqtgraph хранит на оси log10(value),
        поэтому для показа пользователю сначала возвращаемся к "реальному" значению.
        """
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
        """Форматирует наносекунды в ns/µs/ms/s — смотря что лучше читается."""
        ns = float(ns)

        if ns >= 1_000_000_000:
            return f"{ns / 1_000_000_000:.2f} s"
        if ns >= 1_000_000:
            return f"{ns / 1_000_000:.2f} ms"
        if ns >= 1_000:
            return f"{ns / 1_000:.2f} µs"
        return f"{int(ns)} ns"
