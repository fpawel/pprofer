import json
import time
import threading
import requests
from PyQt5 import QtCore


class SseClient(QtCore.QThread):
    event = QtCore.pyqtSignal(object)

    def __init__(self, base_url, topics):
        super().__init__()
        self.base_url = base_url
        self.topics = topics
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
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

                    for line in r.iter_lines(decode_unicode=True):
                        if self._stop.is_set():
                            return

                        if not line:
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
                time.sleep(1)