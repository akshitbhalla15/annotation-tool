import json
import os
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QKeySequence
from PyQt5.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
    QShortcut,
)

from annotation import BoundingBox, ImageAnnotation
from canvas import AnnotationCanvas
from exporter import export_batch
from sidebar_left import LeftSidebar
from sidebar_right import RightSidebar, palette_color


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}


def _collect_images(folder: str) -> List[str]:
    out: List[str] = []
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            out.append(path)
    return out


def _session_path_for_dir(directory: str) -> str:
    return os.path.join(directory, "session.json")


def _box_from_dict(d: dict) -> BoundingBox:
    return BoundingBox(
        int(d["x1"]),
        int(d["y1"]),
        int(d["x2"]),
        int(d["y2"]),
        str(d.get("label", "object")),
    )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Annotation Tool")
        self.resize(1280, 800)

        self._annotations: List[ImageAnnotation] = []
        self._current_index: int = -1
        self._session_dir: Optional[str] = None
        self._undo_stack: List[Tuple[str, BoundingBox]] = []

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Horizontal)
        self._left = LeftSidebar()
        self._canvas = AnnotationCanvas()
        self._right = RightSidebar()
        splitter.addWidget(self._left)
        splitter.addWidget(self._canvas)
        splitter.addWidget(self._right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([220, 800, 280])
        layout.addWidget(splitter)

        self._status = QStatusBar()
        self.setStatusBar(self._status)

        self._left.load_image_clicked.connect(self._on_load_image)
        self._left.load_folder_clicked.connect(self._on_load_folder)
        self._left.prev_clicked.connect(self._prev_image)
        self._left.next_clicked.connect(self._next_image)
        self._left.image_selected.connect(self._go_to_index)

        self._canvas.box_added.connect(self._on_box_added)
        self._canvas.selection_changed.connect(self._on_selection_changed)

        self._right.class_added.connect(self._on_class_added)
        self._right.class_clicked.connect(self._on_class_clicked)
        self._right.export_requested.connect(self._on_export)
        self._right.delete_box_clicked.connect(self._delete_selected)
        self._right.clear_boxes_clicked.connect(self._clear_boxes)
        self._right.save_clicked.connect(self._save_session_manual)

        QShortcut(QKeySequence(Qt.Key_A), self, self._prev_image)
        QShortcut(QKeySequence(Qt.Key_D), self, self._next_image)
        QShortcut(QKeySequence(Qt.Key_Delete), self, self._delete_selected)
        QShortcut(QKeySequence(Qt.Key_S), self, self._save_session_manual)
        QShortcut(QKeySequence(Qt.Key_E), self, self._export_current_only)
        QShortcut(QKeySequence.Undo, self, self._undo)
        for i in range(1, 10):
            QShortcut(QKeySequence(str(i)), self, lambda checked=False, n=i: self._select_class_n(n))

        self._update_class_colors()
        self._refresh_status()

    def _session_file(self) -> Optional[str]:
        if self._session_dir:
            return _session_path_for_dir(self._session_dir)
        return None

    def _set_session_dir_from_path(self, path: str) -> None:
        self._session_dir = os.path.dirname(os.path.abspath(path))

    def _merge_session_json(self, paths: List[str], session_file: str) -> None:
        by_path: Dict[str, List[BoundingBox]] = {}
        if os.path.isfile(session_file):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for item in raw:
                    p = item.get("path")
                    if not p:
                        continue
                    boxes = [_box_from_dict(b) for b in item.get("boxes", [])]
                    by_path[os.path.normpath(p)] = boxes
            except (json.JSONDecodeError, OSError, TypeError, KeyError):
                pass
        self._annotations = []
        for p in paths:
            norm = os.path.normpath(p)
            ann = ImageAnnotation(p, list(by_path.get(norm, [])))
            self._annotations.append(ann)

    def _sync_classes_from_annotations(self) -> None:
        existing = set(self._right.class_names())
        for ann in self._annotations:
            for b in ann.boxes:
                if b.label and b.label not in existing:
                    self._right.add_class_name(b.label)
                    existing.add(b.label)
        self._update_class_colors()

    def _save_session(self) -> None:
        path = self._session_file()
        if not path or not self._annotations:
            return
        data = [
            {"path": a.image_path, "boxes": [vars(b) for b in a.boxes]}
            for a in self._annotations
        ]
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    def _save_session_manual(self) -> None:
        self._save_session()
        if self._session_file():
            self._status.showMessage("Session saved", 2000)
        else:
            self._status.showMessage("Load a folder or image first", 2000)

    def closeEvent(self, event):
        self._save_session()
        super().closeEvent(event)

    def _image_paths(self) -> List[str]:
        return [a.image_path for a in self._annotations]

    def _annotated_flags(self) -> List[bool]:
        return [len(a.boxes) > 0 for a in self._annotations]

    def _refresh_image_list(self) -> None:
        self._left.set_paths(self._image_paths(), self._annotated_flags())
        if 0 <= self._current_index < len(self._annotations):
            self._left.set_current_index(self._current_index)

    def _update_row_check(self, index: int) -> None:
        if 0 <= index < len(self._annotations):
            self._left.update_row_annotation_state(
                index, len(self._annotations[index].boxes) > 0
            )

    def _go_to_index(self, index: int) -> None:
        if index < 0 or index >= len(self._annotations):
            return
        if index == self._current_index:
            return
        self._save_session()
        self._current_index = index
        ann = self._annotations[self._current_index]
        self._canvas.set_annotation(ann)
        self._canvas.load_image_path(ann.image_path)
        self._left.set_current_index(self._current_index)
        self._refresh_status()

    def _prev_image(self) -> None:
        if self._current_index > 0:
            self._go_to_index(self._current_index - 1)

    def _next_image(self) -> None:
        if self._current_index + 1 < len(self._annotations):
            self._go_to_index(self._current_index + 1)

    def _on_load_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;All (*)",
        )
        if not path:
            return
        self._save_session()
        self._set_session_dir_from_path(path)
        session = _session_path_for_dir(self._session_dir or "")
        self._merge_session_json([path], session)
        self._sync_classes_from_annotations()
        self._current_index = -1
        self._refresh_image_list()
        if self._annotations:
            self._go_to_index(0)
        self._undo_stack.clear()

    def _on_load_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open Folder")
        if not folder:
            return
        self._save_session()
        paths = _collect_images(folder)
        if not paths:
            QMessageBox.information(self, "Folder", "No images found in folder.")
            return
        self._session_dir = os.path.abspath(folder)
        session = _session_path_for_dir(self._session_dir)
        self._merge_session_json(paths, session)
        self._sync_classes_from_annotations()
        self._current_index = -1
        self._refresh_image_list()
        self._go_to_index(0)
        self._undo_stack.clear()

    def _update_class_colors(self) -> None:
        names = self._right.class_names()
        colors = {n: palette_color(i) for i, n in enumerate(names)}
        self._canvas.set_class_colors(colors)

    def _on_class_added(self, name: str) -> None:
        self._right.add_class_name(name)
        self._update_class_colors()

    def _on_class_clicked(self, name: str, row: int) -> None:
        self._canvas.set_active_class(name)
        sel = self._canvas.selected_index()
        if sel >= 0 and self._current_index >= 0:
            ann = self._annotations[self._current_index]
            if sel < len(ann.boxes):
                ann.boxes[sel].label = name
                self._canvas.update()
                self._update_row_check(self._current_index)
        self._refresh_status()

    def _on_box_added(self, box: BoundingBox) -> None:
        if self._current_index >= 0:
            ann = self._annotations[self._current_index]
            self._undo_stack.append((ann.image_path, BoundingBox(**vars(box))))
        self._update_row_check(self._current_index)
        self._refresh_status()

    def _on_selection_changed(self, _index: int) -> None:
        self._refresh_status()

    def _delete_selected(self) -> None:
        if self._canvas.delete_selected():
            self._update_row_check(self._current_index)
            self._refresh_status()

    def _clear_boxes(self) -> None:
        if self._current_index < 0:
            return
        self._canvas.clear_all_boxes()
        self._update_row_check(self._current_index)
        self._refresh_status()

    def _undo(self) -> None:
        if not self._undo_stack or self._current_index < 0:
            return
        path, target = self._undo_stack.pop()
        ann = self._annotations[self._current_index]
        if ann.image_path != path:
            self._undo_stack.append((path, target))
            return
        for j in range(len(ann.boxes) - 1, -1, -1):
            b = ann.boxes[j]
            if (
                b.x1 == target.x1
                and b.y1 == target.y1
                and b.x2 == target.x2
                and b.y2 == target.y2
                and b.label == target.label
            ):
                del ann.boxes[j]
                break
        self._canvas.set_annotation(ann)
        self._canvas.load_image_path(ann.image_path)
        self._update_row_check(self._current_index)
        self._refresh_status()

    def _select_class_n(self, n: int) -> None:
        idx = n - 1
        names = self._right.class_names()
        if 0 <= idx < len(names):
            self._right.set_active_class_row(idx)
            self._canvas.set_active_class(names[idx])
            self._refresh_status()

    def _refresh_status(self) -> None:
        total = len(self._annotations)
        cur = self._current_index + 1 if self._current_index >= 0 else 0
        nboxes = self._canvas.box_count()
        klass = self._canvas.active_class() or self._right.active_class_name() or "—"
        zoom = self._canvas.zoom_percent()
        self._status.showMessage(
            f"Image {cur} / {total}   |   Boxes: {nboxes}   |   Class: {klass}   |   Zoom: {zoom}%"
        )

    def _pick_export_dir(self) -> Optional[str]:
        return QFileDialog.getExistingDirectory(self, "Export To Folder")

    def _on_export(self) -> None:
        if not self._annotations:
            QMessageBox.information(self, "Export", "No images loaded.")
            return
        out = self._pick_export_dir()
        if not out:
            return
        classes = self._right.class_names()
        if not classes:
            QMessageBox.warning(
                self,
                "Export",
                "Add at least one class before export (needed for YOLO ids).",
            )
        fmt = self._right.export_format_key()
        crop = self._right.export_crop_enabled()
        size = self._right.export_crop_size()
        try:
            export_batch(self._annotations, classes, out, fmt, crop, size)
        except Exception as e:
            QMessageBox.critical(self, "Export", str(e))
            return
        self._status.showMessage(f"Exported to {out}", 5000)
        QMessageBox.information(self, "Export", f"Exported to:\n{out}")

    def _export_current_only(self) -> None:
        if self._current_index < 0 or not self._annotations:
            self._status.showMessage("No image to export", 2000)
            return
        out = self._pick_export_dir()
        if not out:
            return
        classes = self._right.class_names()
        fmt = self._right.export_format_key()
        crop = self._right.export_crop_enabled()
        size = self._right.export_crop_size()
        one = [self._annotations[self._current_index]]
        try:
            export_batch(one, classes, out, fmt, crop, size)
        except Exception as e:
            QMessageBox.critical(self, "Export", str(e))
            return
        self._status.showMessage(f"Exported current image to {out}", 4000)
