import sys
from PyQt5 import QtWidgets
from .main_window import MainWindow


def run():
    app = QtWidgets.QApplication(sys.argv)

    base_url = "http://127.0.0.1:8080"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]

    window = MainWindow(base_url)
    window.show()

    sys.exit(app.exec_())