import requests
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

        # Для одноразового HTTP-запроса держим отдельную Session:
        # её можно закрыть из stop(), если окно уже закрывается.
        self._session = requests.Session()
        self._stop_requested = False

    def stop(self):
        """
        Просит поток завершиться без отправки результата в GUI.

        Session.close() помогает разбудить поток, если он сейчас ждёт сеть.
        """
        self._stop_requested = True
        self._session.close()

    def run(self):
        """Точка входа потока: делает запрос и сообщает результат через сигналы."""
        if self._stop_requested:
            return

        try:
            labels = get_labels(
                self.base_url,
                session=self._session,
                timeout=(3, 5),
            )
        except Exception as exc:
            # При штатной остановке окно уже закрывается, поэтому
            # лишние ошибки в GUI в этот момент не нужны.
            if not self._stop_requested:
                self.failed.emit(str(exc))
            return
        finally:
            self._session.close()

        if self._stop_requested:
            return

        self.loaded.emit(labels)
