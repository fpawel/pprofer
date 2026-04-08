import signal
import sys

from PyQt5 import QtCore, QtWidgets

from .main_window import MainWindow


def run():
    app = QtWidgets.QApplication(sys.argv)

    base_url = "http://127.0.0.1:8080"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]

    window = MainWindow(base_url)
    window.show()

    signal.signal(signal.SIGINT, lambda *_: app.quit())

    sigint_timer = QtCore.QTimer()
    sigint_timer.start(200)
    sigint_timer.timeout.connect(lambda: None)

    sys.exit(app.exec_())