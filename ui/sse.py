import json
import threading
import time

import requests
from PyQt5 import QtCore


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
        self._stop = threading.Event()

    def stop(self):
        """Просит поток завершиться при ближайшей удобной возможности."""
        self._stop.set()

    def run(self):
        """Поддерживает SSE-подключение и переподключается после ошибок."""
        # Для backend topics передаются как повторяющиеся query-параметры:
        # /events?topic=heap&topic=goroutine...
        params = [("topic", t) for t in self.topics]

        while not self._stop.is_set():
            try:
                with requests.get(
                    f"{self.base_url}/events",
                    params=params,
                    stream=True,
                ) as r:
                    event_type = None
                    data = []

                    # SSE-сообщение состоит из строк вида:
                    # event: heap
                    # data: {...}
                    # и завершается пустой строкой.
                    for line in r.iter_lines(decode_unicode=True):
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

                        if line.startswith("event:"):
                            event_type = line[6:].strip()

                        if line.startswith("data:"):
                            data.append(line[5:].strip())

            except Exception:
                # Для live-viewer важнее не упасть, а попробовать подключиться снова.
                time.sleep(1)
