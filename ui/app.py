import signal
import sys

from PyQt5 import QtCore, QtWidgets

from .main_window import MainWindow


def run():
    """Создаёт QApplication, главное окно и запускает цикл обработки событий Qt."""
    app = QtWidgets.QApplication(sys.argv)

    # По умолчанию UI ходит в локальный backend.
    base_url = "http://127.0.0.1:8080"
    if len(sys.argv) > 1:
        # При запуске можно передать адрес backend первым аргументом.
        base_url = sys.argv[1]

    window = MainWindow(base_url)
    window.show()

    # Позволяем корректно закрывать приложение через Ctrl+C в терминале.
    signal.signal(signal.SIGINT, lambda *_: app.quit())

    # Qt не всегда просыпается от SIGINT сам по себе.
    # Небольшой "пустой" таймер нужен, чтобы event loop регулярно
    # обрабатывал сигналы ОС и можно было завершить приложение из консоли.
    sigint_timer = QtCore.QTimer()
    sigint_timer.start(200)
    sigint_timer.timeout.connect(lambda: None)

    sys.exit(app.exec_())
