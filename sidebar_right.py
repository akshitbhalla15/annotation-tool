from typing import List

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


CLASS_PALETTE = [
    QColor(220, 50, 50),
    QColor(50, 120, 220),
    QColor(50, 180, 80),
    QColor(220, 140, 40),
    QColor(160, 80, 200),
    QColor(40, 200, 200),
    QColor(220, 60, 160),
    QColor(120, 200, 60),
    QColor(100, 100, 240),
    QColor(240, 200, 50),
    QColor(200, 100, 100),
    QColor(80, 160, 140),
    QColor(180, 120, 200),
    QColor(90, 90, 90),
    QColor(255, 128, 0),
]


def palette_color(index: int) -> QColor:
    return CLASS_PALETTE[index % len(CLASS_PALETTE)]


class RightSidebar(QWidget):
    class_added = pyqtSignal(str)
    class_clicked = pyqtSignal(str, int)
    export_requested = pyqtSignal()
    delete_box_clicked = pyqtSignal()
    clear_boxes_clicked = pyqtSignal()
    save_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._classes: List[str] = []
        self._active_row = -1

        root = QVBoxLayout(self)

        root.addWidget(QLabel("Classes"))
        add_row = QHBoxLayout()
        self._edit = QLineEdit()
        self._edit.setPlaceholderText("Class name — Enter to add")
        self._edit.returnPressed.connect(self._add_class)
        add_row.addWidget(self._edit)
        root.addLayout(add_row)

        self._class_list = QListWidget()
        self._class_list.itemClicked.connect(self._on_class_click)
        root.addWidget(self._class_list, 1)

        root.addWidget(QLabel("Export"))
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Size:"))
        self._size_combo = QComboBox()
        self._size_combo.addItems(["320×320", "640×640"])
        size_row.addWidget(self._size_combo)
        root.addLayout(size_row)

        self._crop_check = QCheckBox("Export cropped patches (classification)")
        self._crop_check.setChecked(False)
        root.addWidget(self._crop_check)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(["YOLO .txt", "Pascal VOC .xml", "CSV"])
        fmt_row.addWidget(self._fmt_combo)
        root.addLayout(fmt_row)

        btn_export = QPushButton("Export…")
        btn_export.clicked.connect(self.export_requested.emit)
        root.addWidget(btn_export)

        root.addWidget(QLabel("Editing"))
        btn_del = QPushButton("Delete Selected Box")
        btn_del.clicked.connect(self.delete_box_clicked.emit)
        root.addWidget(btn_del)
        btn_clear = QPushButton("Clear All Boxes")
        btn_clear.clicked.connect(self.clear_boxes_clicked.emit)
        root.addWidget(btn_clear)
        btn_save = QPushButton("Save Annotations")
        btn_save.clicked.connect(self.save_clicked.emit)
        root.addWidget(btn_save)

    def _add_class(self) -> None:
        name = self._edit.text().strip()
        if not name:
            return
        if name not in self._classes:
            self._classes.append(name)
            self._refresh_list()
        self._edit.clear()
        self.class_added.emit(name)
        idx = self._classes.index(name)
        self._class_list.setCurrentRow(idx)
        self._active_row = idx
        self.class_clicked.emit(name, idx)

    def _refresh_list(self) -> None:
        self._class_list.clear()
        for i, name in enumerate(self._classes):
            item = QListWidgetItem(name)
            c = palette_color(i)
            pix = QPixmap(18, 18)
            pix.fill(c)
            item.setIcon(QIcon(pix))
            self._class_list.addItem(item)

    def _on_class_click(self, item: QListWidgetItem) -> None:
        row = self._class_list.row(item)
        if row < 0 or row >= len(self._classes):
            return
        self._active_row = row
        self.class_clicked.emit(self._classes[row], row)

    def set_classes(self, names: List[str]) -> None:
        self._classes = list(names)
        self._refresh_list()

    def add_class_name(self, name: str) -> int:
        if name in self._classes:
            return self._classes.index(name)
        self._classes.append(name)
        self._refresh_list()
        return len(self._classes) - 1

    def class_names(self) -> List[str]:
        return list(self._classes)

    def set_active_class_row(self, index: int) -> None:
        if 0 <= index < self._class_list.count():
            self._class_list.setCurrentRow(index)
            self._active_row = index

    def active_class_name(self) -> str:
        if 0 <= self._active_row < len(self._classes):
            return self._classes[self._active_row]
        return ""

    def export_crop_size(self) -> int:
        return 640 if self._size_combo.currentIndex() == 1 else 320

    def export_crop_enabled(self) -> bool:
        return self._crop_check.isChecked()

    def export_format_key(self) -> str:
        m = {0: "yolo", 1: "voc", 2: "csv"}
        return m.get(self._fmt_combo.currentIndex(), "yolo")

    def focus_class_input(self) -> None:
        self._edit.setFocus()
