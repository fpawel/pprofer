import json
import threading
import time

import requests
from PyQt5 import QtCore
from rich.console import Console


class SseClient(QtCore.QThread):
    """
    Подписчик на SSE-поток backend.

    Backend шлёт события по /events, а этот класс читает поток построчно,
    собирает очередное событие и пробрасывает его в GUI через сигнал.
    """

    event = QtCore.pyqtSignal(object)

    def __init__(self, base_url, topics):
        """Сохраняет адрес backend и список типов профилей, на которые подписываемся."""
        super().__init__()
        self.base_url = base_url
        self.topics = topics

        # Через Event основной поток может попросить run() остановиться.
        self._stop = threading.Event()

        # Session и текущий Response храним как поля, чтобы stop() мог
        # принудительно закрыть активное SSE-соединение.
        self._session = requests.Session()
        self._response = None
        self._response_lock = threading.Lock()

    def stop(self):
        """
        Аккуратно останавливает SSE-поток.

        Важно не только поднять флаг остановки, но и закрыть текущее
        stream-соединение: иначе поток может ещё долго сидеть внутри iter_lines().
        """
        self._stop.set()

        with self._response_lock:
            response = self._response

        if response is not None:
            try:
                response.close()
            except Exception:
                console = Console()
                console.print_exception(show_locals=True)
                pass

        # Закрываем Session в конце, чтобы новые соединения уже не создавались.
        self._session.close()

    def _set_active_response(self, response):
        """Запоминает текущее SSE-соединение, которое при остановке нужно будет закрыть."""
        with self._response_lock:
            self._response = response

    def run(self):
        """Поддерживает SSE-подключение и переподключается после ошибок."""
        # Для backend topics передаются как повторяющиеся query-параметры:
        # /events?topic=heap&topic=goroutine...
        params = [("topic", t) for t in self.topics]

        while not self._stop.is_set():
            response = None

            try:
                # У connect есть timeout, чтобы не зависать навсегда на установке соединения.
                # Для read timeout используем None: SSE может долго молчать между событиями,
                # и это не должно считаться ошибкой. Останавливаем такой поток через response.close().
                response = self._session.get(
                    f"{self.base_url}/events",
                    params=params,
                    stream=True,
                    timeout=(3, None),
                )
                response.raise_for_status()
                self._set_active_response(response)

                event_type = None
                data = []

                # SSE-сообщение состоит из строк вида:
                # event: heap
                # data: {...}
                # и завершается пустой строкой.
                for line in response.iter_lines(decode_unicode=True):
                    if self._stop.is_set():
                        return

                    if not line:
                        # Пустая строка означает "событие закончено" —
                        # можно собрать накопленные data-строки в один JSON.
                        if event_type and data:
                            payload = json.loads("\n".join(data))
                            payload["_type"] = event_type
                            payload["_ts"] = time.time()
                            self.event.emit(payload)

                        event_type = None
                        data = []
                        continue

                    # Комментарии и keepalive-строки в SSE начинаются с ":".
                    # Для графика они не несут полезной нагрузки.
                    if line.startswith(":"):
                        continue

                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                        continue

                    if line.startswith("data:"):
                        data.append(line[5:].strip())

            except Exception:
                console = Console()
                console.print_exception(show_locals=True)
                # Для live-viewer важнее не упасть, а попробовать подключиться снова.
                # Но во время штатного shutdown сразу выходим без лишней паузы.
                if self._stop.wait(1):
                    return
            finally:
                self._set_active_response(None)
                if response is not None:
                    try:
                        response.close()
                    except Exception:
                        console = Console()
                        console.print_exception(show_locals=True)
                        pass
