from PyQt5 import QtCore

from .app_service_client import get_labels


class LabelsFetchThread(QtCore.QThread):
    loaded = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str)

    def __init__(self, base_url, parent=None):
        super().__init__(parent)
        self.base_url = base_url

    def run(self):
        try:
            labels = get_labels(self.base_url)
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        self.loaded.emit(labels)