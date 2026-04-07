from PyQt5 import QtGui


class StackTraceHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)

        self.func_format = QtGui.QTextCharFormat()
        self.func_format.setForeground(QtGui.QColor("#1f4e79"))
        self.func_format.setFontWeight(QtGui.QFont.Bold)

        self.file_format = QtGui.QTextCharFormat()
        self.file_format.setForeground(QtGui.QColor("#555555"))

        self.line_number_format = QtGui.QTextCharFormat()
        self.line_number_format.setForeground(QtGui.QColor("#b35a00"))
        self.line_number_format.setFontWeight(QtGui.QFont.Bold)

        self.first_frame_background = QtGui.QTextCharFormat()
        self.first_frame_background.setBackground(QtGui.QColor("#fff3cd"))

        self.info_format = QtGui.QTextCharFormat()
        self.info_format.setForeground(QtGui.QColor("#777777"))
        self.info_format.setFontItalic(True)

    def highlightBlock(self, text):
        if not text:
            return

        stripped = text.strip()

        if (
            stripped.startswith("Загрузка")
            or stripped.startswith("Не удалось")
            or stripped.startswith("Стектрейс недоступен")
            or stripped.startswith("Выбери серию")
        ):
            self.setFormat(0, len(text), self.info_format)
            return

        if stripped and stripped[0].isdigit() and ". " in stripped:
            if stripped.startswith("1."):
                self.setFormat(0, len(text), self.first_frame_background)
            self.setFormat(0, len(text), self.func_format)
            return

        if text.startswith("    "):
            pos = text.rfind(":")
            if pos > 0 and text[pos + 1 :].strip().isdigit():
                self.setFormat(0, pos, self.file_format)
                self.setFormat(pos, len(text) - pos, self.line_number_format)
                return

            self.setFormat(0, len(text), self.file_format)
