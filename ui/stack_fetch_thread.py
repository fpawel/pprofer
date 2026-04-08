import requests
from PyQt5 import QtCore

from .app_service_client import get_stack


class StackFetchThread(QtCore.QThread):
    """
    Поток для загрузки stack trace выбранной серии.

    request_id нужен для защиты от гонки:
    если пользователь быстро переключил выбор, старый ответ можно игнорировать.
    """

    loaded = QtCore.pyqtSignal(int, object)
    failed = QtCore.pyqtSignal(int, str)

    def __init__(self, base_url, func, line, inline, request_id, parent=None):
        """Сохраняет параметры поиска stack trace и идентификатор запроса."""
        super().__init__(parent)
        self.base_url = base_url
        self.func = func
        self.line = line
        self.inline = inline
        self.request_id = request_id

        # Отдельная Session нужна, чтобы конкретный запрос можно было
        # закрыть независимо от остальных потоков и от SSE-клиента.
        self._session = requests.Session()
        self._stop_requested = False

    def stop(self):
        """
        Просит поток завершиться без обновления UI.

        Это важно в двух сценариях:
        - пользователь быстро выбрал другую серию;
        - окно закрывается и стектрейс уже никому не нужен.
        """
        self._stop_requested = True
        self._session.close()

    def run(self):
        """Запрашивает stack trace и отправляет результат обратно в GUI через сигналы."""
        if self._stop_requested:
            return

        try:
            frames = get_stack(
                base_url=self.base_url,
                func=self.func,
                line=self.line,
                inline=self.inline,
                session=self._session,
                timeout=(3, 10),
            )
        except Exception as exc:
            if not self._stop_requested:
                self.failed.emit(self.request_id, str(exc))
            return
        finally:
            self._session.close()

        if self._stop_requested:
            return

        self.loaded.emit(self.request_id, frames)
