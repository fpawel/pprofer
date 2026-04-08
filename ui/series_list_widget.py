from PyQt5 import QtCore, QtGui, QtWidgets


class SeriesListWidget(QtWidgets.QWidget):
    """
    Правая панель со списком серий.

    Она не хранит свои данные отдельно, а каждый раз читает актуальное состояние
    из PlotWidget. Это упрощает синхронизацию между списком и графиком.
    """

    series_selected = QtCore.pyqtSignal(str)

    def __init__(self, plot_widget, parent=None):
        """Привязывает список к конкретному PlotWidget."""
        super().__init__(parent)
        self.plot_widget = plot_widget
        self._selected_key = None
        self._items_by_key = {}

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(8)

        title = QtWidgets.QLabel("Series")
        title.setStyleSheet("font-weight: bold; font-size: 15px;")
        root_layout.addWidget(title)

        buttons_layout = QtWidgets.QHBoxLayout()
        self.select_all_button = QtWidgets.QPushButton("Show all")
        self.hide_all_button = QtWidgets.QPushButton("Hide all")
        buttons_layout.addWidget(self.select_all_button)
        buttons_layout.addWidget(self.hide_all_button)
        root_layout.addLayout(buttons_layout)

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.setStyleSheet("""
            QListWidget {
                font-size: 15px;
            }
            QListWidget::item {
                padding: 6px 4px;
            }
        """)
        root_layout.addWidget(self.list_widget, 1)

        self.select_all_button.clicked.connect(self.show_all)
        self.hide_all_button.clicked.connect(self.hide_all)
        self.list_widget.currentItemChanged.connect(self._on_current_item_changed)
        self.list_widget.itemChanged.connect(self._on_item_changed)

    def current_key(self):
        """Возвращает ключ выбранной серии или None."""
        return self._selected_key

    def _on_current_item_changed(self, current, _previous):
        """Реагирует на смену выделенного элемента списка."""
        if current is None:
            self._selected_key = None
            self.series_selected.emit("")
            return

        key = current.data(QtCore.Qt.UserRole)
        self._selected_key = key

        # Держим выбранный элемент в видимой области списка.
        self.list_widget.scrollToItem(current, QtWidgets.QAbstractItemView.EnsureVisible)
        self.series_selected.emit(key)

    def _on_item_changed(self, item):
        """Реагирует на изменение галочки у элемента списка."""
        key = item.data(QtCore.Qt.UserRole)
        visible = item.checkState() == QtCore.Qt.Checked
        self.plot_widget.set_series_visible(key, visible)

    def refresh_visible_series(self):
        """
        Полностью пересобирает список видимых/активных серий.

        Здесь источник истины — PlotWidget:
        список просто отражает его текущее состояние.
        """
        if self.plot_widget.show_all_series:
            keys = list(self.plot_widget.data.keys())
        else:
            keys = list(self.plot_widget.visible_series_keys())

        # Если пользователь выбрал серию, оставляем её в списке,
        # даже если она уже не входит в top N.
        if self._selected_key and self._selected_key in self.plot_widget.data and self._selected_key not in keys:
            keys.append(self._selected_key)

        keys.sort(key=lambda k: self.plot_widget.series_score(k), reverse=True)

        final_key = self._selected_key
        if final_key not in keys:
            final_key = keys[0] if keys else None

        self._items_by_key = {}

        # На время полной пересборки отключаем сигналы,
        # чтобы не вызвать лишние реакции на промежуточные состояния.
        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        item_font = self.list_widget.font()
        item_font.setPointSize(15)

        for key in keys:
            name = self.plot_widget.series_names.get(key, key)
            color = self.plot_widget.color_for_key(key)

            item = QtWidgets.QListWidgetItem(name)
            item.setData(QtCore.Qt.UserRole, key)
            item.setFlags(
                QtCore.Qt.ItemIsEnabled
                | QtCore.Qt.ItemIsSelectable
                | QtCore.Qt.ItemIsUserCheckable
            )
            item.setCheckState(
                QtCore.Qt.Checked
                if self.plot_widget.series_visible.get(key, True)
                else QtCore.Qt.Unchecked
            )
            item.setForeground(QtGui.QColor(color))
            item.setFont(item_font)

            self.list_widget.addItem(item)
            self._items_by_key[key] = item

        if final_key is not None and final_key in self._items_by_key:
            self.list_widget.setCurrentItem(self._items_by_key[final_key])
            self.list_widget.scrollToItem(
                self._items_by_key[final_key],
                QtWidgets.QAbstractItemView.EnsureVisible,
            )

        self.list_widget.blockSignals(False)

        if final_key != self._selected_key:
            self._selected_key = final_key
            self.series_selected.emit(final_key or "")

    def show_all(self):
        """Ставит галочки у всех элементов списка и показывает все активные серии."""
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setCheckState(QtCore.Qt.Checked)
            key = item.data(QtCore.Qt.UserRole)
            self.plot_widget.set_series_visible(key, True)
        self.list_widget.blockSignals(False)

    def hide_all(self):
        """Снимает галочки у всех элементов списка и скрывает все активные серии."""
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setCheckState(QtCore.Qt.Unchecked)
            key = item.data(QtCore.Qt.UserRole)
            self.plot_widget.set_series_visible(key, False)
        self.list_widget.blockSignals(False)
