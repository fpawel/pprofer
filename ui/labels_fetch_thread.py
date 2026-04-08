from PyQt5 import QtCore

from .app_service_client import get_labels


class LabelsFetchThread(QtCore.QThread):
    """
    Отдельный поток для загрузки labels.

    Зачем нужен QThread:
    HTTP-запрос может занять заметное время, а UI должен оставаться отзывчивым.
    """

    loaded = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str)

    def __init__(self, base_url, parent=None):
        """Сохраняет адрес backend, у которого будем спрашивать labels."""
        super().__init__(parent)
        self.base_url = base_url

    def run(self):
        """Точка входа потока: делает запрос и сообщает результат через сигналы."""
        try:
            labels = get_labels(self.base_url)
        except Exception as exc:
            # Исключение нельзя просто пробросить в GUI-поток,
            # поэтому передаём текст ошибки через сигнал.
            self.failed.emit(str(exc))
            return

        self.loaded.emit(labels)
