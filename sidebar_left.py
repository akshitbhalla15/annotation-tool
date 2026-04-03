import os
from typing import List, Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LeftSidebar(QWidget):
    load_image_clicked = pyqtSignal()
    load_folder_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    image_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paths: List[str] = []

        root = QVBoxLayout(self)
        btn_load = QPushButton("Load Image")
        btn_load.clicked.connect(self.load_image_clicked.emit)
        btn_folder = QPushButton("Load Folder")
        btn_folder.clicked.connect(self.load_folder_clicked.emit)
        root.addWidget(btn_load)
        root.addWidget(btn_folder)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row)
        root.addWidget(self._list, 1)

        self._name = QLabel("—")
        self._name.setWordWrap(True)
        root.addWidget(self._name)

        nav = QHBoxLayout()
        self._btn_prev = QPushButton("Previous")
        self._btn_next = QPushButton("Next")
        self._btn_prev.clicked.connect(self.prev_clicked.emit)
        self._btn_next.clicked.connect(self.next_clicked.emit)
        nav.addWidget(self._btn_prev)
        nav.addWidget(self._btn_next)
        root.addLayout(nav)

    def _on_row(self, row: int) -> None:
        if row >= 0:
            self.image_selected.emit(row)

    def set_paths(self, paths: List[str], annotated: Optional[List[bool]] = None) -> None:
        self._paths = list(paths)
        self._list.blockSignals(True)
        self._list.clear()
        for i, p in enumerate(paths):
            item = QListWidgetItem(os.path.basename(p))
            if annotated and i < len(annotated) and annotated[i]:
                item.setText("✓ " + item.text())
            self._list.addItem(item)
        self._list.blockSignals(False)

    def update_row_annotation_state(self, index: int, has_boxes: bool) -> None:
        if index < 0 or index >= self._list.count():
            return
        item = self._list.item(index)
        base = os.path.basename(self._paths[index]) if index < len(self._paths) else item.text().lstrip("✓ ").strip()
        item.setText(("✓ " if has_boxes else "") + base)

    def set_current_index(self, index: int) -> None:
        if 0 <= index < self._list.count():
            self._list.blockSignals(True)
            self._list.setCurrentRow(index)
            self._list.blockSignals(False)
        if 0 <= index < len(self._paths):
            self._name.setText(os.path.basename(self._paths[index]))
        else:
            self._name.setText("—")

    def current_list_index(self) -> int:
        return self._list.currentRow()
