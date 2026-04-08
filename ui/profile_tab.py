from html import escape

from PyQt5 import QtWidgets, QtCore, QtGui

from ui.plot_widget import PlotWidget
from ui.series_list_widget import SeriesListWidget
from ui.stack_fetch_thread import StackFetchThread
from ui.stack_trace_highlighter import StackTraceHighlighter


class ProfileTab(QtWidgets.QWidget):
    def __init__(self, base_url, profile_name, mode, max_visible_series=10, view_seconds=300, parent=None):
        super().__init__(parent)

        self.base_url = base_url
        self.profile_name = profile_name
        self._stack_request_id = 0

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        controls_layout = QtWidgets.QHBoxLayout()

        self.follow_live_checkbox = QtWidgets.QCheckBox("Follow live")
        self.follow_live_checkbox.setChecked(True)
        controls_layout.addWidget(self.follow_live_checkbox)

        self.view_all_button = QtWidgets.QPushButton("View all")
        controls_layout.addWidget(self.view_all_button)

        self.top_n_button = QtWidgets.QPushButton("Top 10")
        controls_layout.addWidget(self.top_n_button)

        self.sort_combo = QtWidgets.QComboBox()
        self.sort_combo.addItems(["last", "avg", "max"])
        controls_layout.addWidget(self.sort_combo)

        self.labels_title = QtWidgets.QLabel("Labels:")
        self.labels_title.setStyleSheet("font-weight: 600;")
        controls_layout.addWidget(self.labels_title)

        self.labels_value = QtWidgets.QLineEdit()
        self.labels_value.setReadOnly(True)
        self.labels_value.setPlaceholderText("Waiting for labels...")
        self.labels_value.setMinimumWidth(320)
        controls_layout.addWidget(self.labels_value, 1)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        outer_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        layout.addWidget(outer_splitter)

        self.plot = PlotWidget(
            profile_name,
            mode=mode,
            max_visible_series=max_visible_series,
            view_seconds=view_seconds,
            log_y=profile_name in LOG_SCALE_PROFILES,
        )
        outer_splitter.addWidget(self.plot)

        right_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        outer_splitter.addWidget(right_splitter)

        self.series_list = SeriesListWidget(self.plot)
        self.series_list.setMinimumWidth(380)
        right_splitter.addWidget(self.series_list)

        stack_panel = QtWidgets.QWidget()
        stack_layout = QtWidgets.QVBoxLayout(stack_panel)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.setSpacing(6)

        stack_title = QtWidgets.QLabel("Stack trace")
        stack_title.setStyleSheet("font-weight: bold; font-size: 15px;")
        stack_layout.addWidget(stack_title)

        self.stack_series_label = QtWidgets.QLabel()
        self.stack_series_label.setWordWrap(True)
        self.stack_series_label.setTextFormat(QtCore.Qt.RichText)
        self.stack_series_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.stack_series_label.setStyleSheet("""
            QLabel {
                background: #fcfcfc;
                border: 1px solid #d8d8d8;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        self.stack_series_label.setText(format_series_header_html("", ""))
        stack_layout.addWidget(self.stack_series_label)

        self.stack_view = QtWidgets.QPlainTextEdit()
        self.stack_view.setReadOnly(True)
        self.stack_view.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)

        font = QtGui.QFont("Consolas")
        font.setStyleHint(QtGui.QFont.Monospace)
        font.setPointSize(14)
        self.stack_view.setFont(font)

        self.stack_view.setTabStopDistance(32)
        self.stack_view.setStyleSheet("""
            QPlainTextEdit {
                background: #fcfcfc;
                border: 1px solid #d8d8d8;
                padding: 8px;
                selection-background-color: #cfe8ff;
            }
        """)
        self.stack_highlighter = StackTraceHighlighter(self.stack_view.document())
        self.stack_view.setPlainText("Выбери серию справа, чтобы увидеть стектрейс.")
        stack_layout.addWidget(self.stack_view, 1)

        right_splitter.addWidget(stack_panel)

        outer_splitter.setStretchFactor(0, 1)
        outer_splitter.setStretchFactor(1, 0)
        outer_splitter.setSizes([1100, 440])

        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 1)
        right_splitter.setSizes([420, 340])

        self.follow_live_checkbox.toggled.connect(self.plot.set_follow_live)
        self.view_all_button.clicked.connect(self.plot.view_all)
        self.top_n_button.clicked.connect(self.on_show_top_n)
        self.sort_combo.currentTextChanged.connect(self.on_sort_changed)
        self.plot.manual_view_activated.connect(self._on_manual_view_activated)
        self.series_list.series_selected.connect(self.on_series_selected)

    def set_labels(self, labels):
        if not labels:
            self.labels_value.clear()
            self.labels_value.setPlaceholderText("Waiting for labels...")
            return

        self.labels_value.setText(", ".join(labels))

    def _on_manual_view_activated(self):
        self.follow_live_checkbox.blockSignals(True)
        self.follow_live_checkbox.setChecked(False)
        self.follow_live_checkbox.blockSignals(False)

    def on_show_top_n(self):
        self.plot.show_top_n()

    def on_sort_changed(self, mode):
        self.plot.sort_mode = mode

    def on_series_selected(self, key):
        self.plot.set_selected_series(key)

        if not key:
            self.stack_series_label.setText(format_series_header_html("", ""))
            self.stack_view.setPlainText("Выбери серию справа, чтобы увидеть стектрейс.")
            return

        meta = self.plot.series_meta.get(key) or {}
        func = meta.get("func", "")
        line = meta.get("line", "")
        inline = meta.get("inline", "")

        self.stack_series_label.setText(format_series_header_html(func, inline))
        self.stack_view.setPlainText("Загрузка стектрейса...")

        self._stack_request_id += 1
        request_id = self._stack_request_id

        thread = StackFetchThread(
            base_url=self.base_url,
            func=func,
            line=line,
            inline=inline,
            request_id=request_id,
            parent=self,
        )
        thread.loaded.connect(self._on_stack_loaded)
        thread.failed.connect(self._on_stack_failed)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _on_stack_loaded(self, request_id, frames):
        if request_id != self._stack_request_id:
            return
        self.stack_view.setPlainText(format_stack_frames(frames))

    def _on_stack_failed(self, request_id, error_text):
        if request_id != self._stack_request_id:
            return
        self.stack_view.setPlainText(f"Не удалось загрузить стектрейс.\n\n{error_text}")


def format_stack_frames(frames):
    if not frames:
        return "Стектрейс недоступен."

    lines = []
    for index, frame in enumerate(frames, 1):
        func = frame.get("function") or "<unknown>"
        file = frame.get("file") or ""
        line = frame.get("line")

        lines.append(f"{index:>2}. {func}")
        if file:
            if line:
                lines.append(f"    {file}:{line}")
            else:
                lines.append(f"    {file}")

    return "\n".join(lines)


def format_series_header_html(func, inline):
    if not func:
        return '<span style="color:#777777; font-size:15px;">Серия не выбрана</span>'

    blocks = []

    blocks.append(
        f"""
        <div style="
            font-size: 22px;
            font-weight: 700;
            color: #1f4e79;
            margin-bottom: 6px;
        ">
            {escape(func)}
        </div>
        """
    )

    if inline:
        blocks.append(
            f"""
            <div>
                <span style="
                    background: #fff3cd;
                    color: #7a4f00;
                    border: 1px solid #e6d28a;
                    border-radius: 10px;
                    padding: 2px 8px;
                    font-size: 13px;
                    font-weight: 600;
                ">
                    {escape(inline)}
                </span>
            </div>
            """
        )

    return "".join(blocks)


LOG_SCALE_PROFILES = {"heap", "allocs", "profile", "block", "mutex"}
