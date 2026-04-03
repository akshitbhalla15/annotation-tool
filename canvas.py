from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QCursor, QFont, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QWidget

from annotation import BoundingBox, ImageAnnotation
from utils import clamp, fit_size

# Widget pixels — hit target and drawn handle size (screen-space).
HANDLE_HALF = 6


class AnnotationCanvas(QWidget):
    box_added = pyqtSignal(object)
    selection_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(400, 300)

        self._annotation: Optional[ImageAnnotation] = None
        self._pixmap_orig: Optional[QPixmap] = None
        self._orig_w = 0
        self._orig_h = 0
        self._disp_w = 0
        self._disp_h = 0
        self._off_x = 0
        self._off_y = 0

        self._active_class = ""
        self._class_colors: Dict[str, QColor] = {}
        self._default_color = QColor(200, 200, 200)

        self._selected_index: int = -1
        self._drag_start: Optional[Tuple[int, int]] = None
        self._drag_current: Optional[Tuple[int, int]] = None

        # Resize: which corner (0=NW,1=NE,2=SE,3=SW) and fixed opposite corner / edges from press.
        self._resize_corner: Optional[int] = None
        self._resize_orig: Optional[Tuple[int, int, int, int]] = None

    def set_class_colors(self, colors: Dict[str, QColor]) -> None:
        self._class_colors = dict(colors)
        self.update()

    def set_active_class(self, name: str) -> None:
        self._active_class = name or ""

    def active_class(self) -> str:
        return self._active_class

    def selected_index(self) -> int:
        return self._selected_index

    def set_annotation(self, ann: Optional[ImageAnnotation]) -> None:
        self._annotation = ann
        self._selected_index = -1
        self._drag_start = None
        self._drag_current = None
        self._resize_corner = None
        self._resize_orig = None
        self.update()

    def load_image_path(self, path: Optional[str]) -> None:
        self._pixmap_orig = None
        self._orig_w = self._orig_h = 0
        self._drag_start = None
        self._drag_current = None
        self._resize_corner = None
        self._resize_orig = None
        if not path:
            self.update()
            return
        img = QImage(path)
        if img.isNull():
            self.update()
            return
        self._pixmap_orig = QPixmap.fromImage(img)
        self._orig_w = self._pixmap_orig.width()
        self._orig_h = self._pixmap_orig.height()
        self._recalc_layout()
        self.update()

    def clear_selection(self) -> None:
        if self._selected_index >= 0:
            self._selected_index = -1
            self.selection_changed.emit(-1)
            self.update()

    def delete_selected(self) -> bool:
        if (
            self._selected_index < 0
            or not self._annotation
            or self._selected_index >= len(self._annotation.boxes)
        ):
            return False
        del self._annotation.boxes[self._selected_index]
        self._selected_index = -1
        self.selection_changed.emit(-1)
        self.update()
        return True

    def clear_all_boxes(self) -> None:
        if not self._annotation:
            return
        self._annotation.boxes.clear()
        self._selected_index = -1
        self.selection_changed.emit(-1)
        self.update()

    def _recalc_layout(self) -> None:
        if not self._pixmap_orig or self._orig_w <= 0:
            self._disp_w = self._disp_h = 0
            self._off_x = self._off_y = 0
            return
        cw, ch = self.width(), self.height()
        self._disp_w, self._disp_h = fit_size(self._orig_w, self._orig_h, cw, ch)
        self._off_x = (cw - self._disp_w) // 2
        self._off_y = (ch - self._disp_h) // 2

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._recalc_layout()

    def _widget_to_image(self, wx: int, wy: int) -> Optional[Tuple[int, int]]:
        if not self._pixmap_orig or self._disp_w <= 0 or self._disp_h <= 0:
            return None
        lx = wx - self._off_x
        ly = wy - self._off_y
        if lx < 0 or ly < 0 or lx >= self._disp_w or ly >= self._disp_h:
            return None
        ix = int(round(lx * self._orig_w / self._disp_w))
        iy = int(round(ly * self._orig_h / self._disp_h))
        ix = max(0, min(self._orig_w - 1, ix))
        iy = max(0, min(self._orig_h - 1, iy))
        return ix, iy

    def _image_to_widget(self, ix: int, iy: int) -> Tuple[int, int]:
        wx = self._off_x + int(round(ix * self._disp_w / self._orig_w))
        wy = self._off_y + int(round(iy * self._disp_h / self._orig_h))
        return wx, wy

    def _hit_test(self, ix: int, iy: int) -> int:
        if not self._annotation:
            return -1
        boxes = self._annotation.boxes
        for i in range(len(boxes) - 1, -1, -1):
            b = boxes[i]
            x1, y1, x2, y2 = b.normalized()
            if x1 <= ix <= x2 and y1 <= iy <= y2:
                return i
        return -1

    def _hit_handle(self, mx: int, my: int) -> int:
        """Return corner index 0..3 if (mx,my) hits a handle on the selected box, else -1."""
        if (
            self._selected_index < 0
            or not self._annotation
            or self._selected_index >= len(self._annotation.boxes)
        ):
            return -1
        b = self._annotation.boxes[self._selected_index]
        x1, y1, x2, y2 = b.normalized()
        wx1, wy1 = self._image_to_widget(x1, y1)
        wx2, wy2 = self._image_to_widget(x2, y2)
        corners = [(wx1, wy1), (wx2, wy1), (wx2, wy2), (wx1, wy2)]
        h = HANDLE_HALF
        for i, (cx, cy) in enumerate(corners):
            if abs(mx - cx) <= h and abs(my - cy) <= h:
                return i
        return -1

    def _cursor_for_corner(self, corner: int) -> QCursor:
        if corner in (0, 2):
            return QCursor(Qt.SizeFDiagCursor)
        return QCursor(Qt.SizeBDiagCursor)

    def _update_hover_cursor(self, mx: int, my: int) -> None:
        if not self._pixmap_orig or self._disp_w <= 0:
            self.unsetCursor()
            return
        c = self._hit_handle(mx, my)
        if c >= 0:
            self.setCursor(self._cursor_for_corner(c))
        else:
            self.unsetCursor()

    MIN_BOX = 3

    def _apply_resize(self, ix: int, iy: int) -> None:
        if (
            self._resize_corner is None
            or self._resize_orig is None
            or not self._annotation
            or self._selected_index < 0
            or self._selected_index >= len(self._annotation.boxes)
        ):
            return
        ox1, oy1, ox2, oy2 = self._resize_orig
        m = self.MIN_BOX
        ow, oh = max(1, self._orig_w - 1), max(1, self._orig_h - 1)
        b = self._annotation.boxes[self._selected_index]
        c = self._resize_corner
        if c == 0:
            nx1 = clamp(ix, 0, max(0, ox2 - m))
            ny1 = clamp(iy, 0, max(0, oy2 - m))
            b.x1, b.y1, b.x2, b.y2 = nx1, ny1, ox2, oy2
        elif c == 1:
            nx2 = clamp(ix, min(ow, ox1 + m), ow)
            ny1 = clamp(iy, 0, max(0, oy2 - m))
            b.x1, b.y1, b.x2, b.y2 = ox1, ny1, nx2, oy2
        elif c == 2:
            nx2 = clamp(ix, min(ow, ox1 + m), ow)
            ny2 = clamp(iy, min(oh, oy1 + m), oh)
            b.x1, b.y1, b.x2, b.y2 = ox1, oy1, nx2, ny2
        else:
            nx1 = clamp(ix, 0, max(0, ox2 - m))
            ny2 = clamp(iy, min(oh, oy1 + m), oh)
            b.x1, b.y1, b.x2, b.y2 = nx1, oy1, ox2, ny2

    def leaveEvent(self, event):
        self.unsetCursor()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.LeftButton:
            return
        if not self._pixmap_orig or not self._annotation:
            return
        mx, my = event.x(), event.y()
        hi = self._hit_handle(mx, my)
        if hi >= 0:
            self._resize_corner = hi
            b = self._annotation.boxes[self._selected_index]
            self._resize_orig = tuple(b.normalized())
            self._drag_start = None
            self._drag_current = None
            self.setCursor(self._cursor_for_corner(hi))
            self.update()
            return

        pos = self._widget_to_image(mx, my)
        if pos is None:
            self._drag_start = None
            self._drag_current = None
            self._resize_corner = None
            self._resize_orig = None
            if self._selected_index >= 0:
                self._selected_index = -1
                self.selection_changed.emit(-1)
                self.update()
            return
        ix, iy = pos
        hit = self._hit_test(ix, iy)
        if hit >= 0:
            self._drag_start = None
            self._drag_current = None
            self._resize_corner = None
            self._resize_orig = None
            self._selected_index = hit
            self.selection_changed.emit(hit)
            self.update()
            return
        self._selected_index = -1
        self.selection_changed.emit(-1)
        self._resize_corner = None
        self._resize_orig = None
        self._drag_start = (ix, iy)
        self._drag_current = (ix, iy)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        mx, my = event.x(), event.y()
        if self._resize_corner is not None and event.buttons() & Qt.LeftButton:
            pos = self._widget_to_image(mx, my)
            if pos:
                self._apply_resize(*pos)
            self.update()
            return
        if self._drag_start is not None:
            pos = self._widget_to_image(mx, my)
            if pos is None:
                return
            self._drag_current = pos
            self.update()
            return
        if not event.buttons() & Qt.LeftButton:
            self._update_hover_cursor(mx, my)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() != Qt.LeftButton:
            return
        if self._resize_corner is not None:
            self._resize_corner = None
            self._resize_orig = None
            self._update_hover_cursor(event.x(), event.y())
            self.update()
            return
        if self._drag_start is None:
            return
        pos = self._widget_to_image(event.x(), event.y())
        if pos is None or not self._annotation:
            self._drag_start = None
            self._drag_current = None
            self.update()
            return
        x1, y1 = self._drag_start
        x2, y2 = pos
        self._drag_start = None
        self._drag_current = None
        w = abs(x2 - x1)
        h = abs(y2 - y1)
        if w < 3 or h < 3:
            self.update()
            return
        label = self._active_class.strip() or "object"
        box = BoundingBox(
            min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2), label
        )
        self._annotation.boxes.append(box)
        self._selected_index = len(self._annotation.boxes) - 1
        self.selection_changed.emit(self._selected_index)
        self.box_added.emit(box)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(40, 40, 45))

        if not self._pixmap_orig or self._disp_w <= 0:
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(self.rect(), Qt.AlignCenter, "No image loaded")
            return

        scaled = self._pixmap_orig.scaled(
            self._disp_w,
            self._disp_h,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        painter.drawPixmap(self._off_x, self._off_y, scaled)

        if self._annotation:
            for i, b in enumerate(self._annotation.boxes):
                self._draw_box(painter, b, i == self._selected_index)
            if 0 <= self._selected_index < len(self._annotation.boxes):
                self._draw_corner_handles(
                    painter, self._annotation.boxes[self._selected_index]
                )

        if self._drag_start and self._drag_current:
            wx1, wy1 = self._image_to_widget(*self._drag_start)
            wx2, wy2 = self._image_to_widget(*self._drag_current)
            pen = QPen(QColor(255, 220, 0))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(
                min(wx1, wx2),
                min(wy1, wy2),
                abs(wx2 - wx1),
                abs(wy2 - wy1),
            )

    def _draw_box(self, painter: QPainter, b: BoundingBox, selected: bool) -> None:
        x1, y1, x2, y2 = b.normalized()
        wx1, wy1 = self._image_to_widget(x1, y1)
        wx2, wy2 = self._image_to_widget(x2, y2)
        color = self._class_colors.get(b.label, self._default_color)
        pen = QPen(color if not selected else QColor(255, 255, 100))
        pen.setWidth(3 if selected else 2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(wx1, wy1, wx2 - wx1, wy2 - wy1)

        tag = b.label
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(tag) + 8
        th = fm.height() + 4
        ty = wy1 - th
        if ty < 0:
            ty = wy1
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawRect(wx1, ty, tw, th)
        lum = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
        painter.setPen(
            QColor(0, 0, 0) if lum > 160 else QColor(255, 255, 255)
        )
        painter.drawText(wx1 + 4, ty + th - 6, tag)

    def _draw_corner_handles(self, painter: QPainter, b: BoundingBox) -> None:
        x1, y1, x2, y2 = b.normalized()
        wx1, wy1 = self._image_to_widget(x1, y1)
        wx2, wy2 = self._image_to_widget(x2, y2)
        hs = HANDLE_HALF
        painter.setPen(QPen(QColor(40, 40, 40), 1))
        painter.setBrush(QColor(255, 255, 255))
        for cx, cy in ((wx1, wy1), (wx2, wy1), (wx2, wy2), (wx1, wy2)):
            painter.drawRect(cx - hs, cy - hs, hs * 2, hs * 2)

    def box_count(self) -> int:
        if not self._annotation:
            return 0
        return len(self._annotation.boxes)

    def zoom_percent(self) -> int:
        if not self._pixmap_orig or self._orig_w <= 0:
            return 100
        return int(round(100 * self._disp_w / self._orig_w))
