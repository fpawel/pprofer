from PyQt5 import QtCore
from .app_service_client import get_stack

class StackFetchThread(QtCore.QThread):
    loaded = QtCore.pyqtSignal(int, object)
    failed = QtCore.pyqtSignal(int, str)

    def __init__(self, base_url, func, line, inline, request_id, parent=None):
        super().__init__(parent)
        self.base_url = base_url
        self.func = func
        self.line = line
        self.inline = inline
        self.request_id = request_id

    def run(self):
        try:
            frames = get_stack(
                base_url=self.base_url,
                func=self.func,
                line=self.line,
                inline=self.inline,
            )
        except Exception as exc:
            self.failed.emit(self.request_id, str(exc))
            return

        self.loaded.emit(self.request_id, frames)