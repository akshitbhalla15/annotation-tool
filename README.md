# Image Annotation Tool

A desktop app for drawing bounding boxes on images, labeling them, and exporting data for **object detection** or **classification** workflows. Built with **PyQt5** and **Pillow**.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-green.svg)

## Features

- **Load** a single image or an entire folder (`.jpg`, `.jpeg`, `.png`, `.bmp`, `.gif`, `.webp`).
- **Draw** boxes by click-and-drag; coordinates are stored in **original image pixel space** (zoom is display-only).
- **Classes** with a fixed color palette; add names from the right panel and pick the active class before drawing.
- **Select** a box by clicking it; **delete**, **relabel** (click a class while a box is selected), or **resize** using the **corner handles** on the selected box.
- **Navigate** the image list with buttons or the list widget; annotated images show a checkmark (✓) in the queue.
- **Export** to YOLO (normalized `.txt` + `classes.txt`), Pascal VOC (`.xml`), or CSV; optionally export **square cropped patches** at **320×320** or **640×640** for classification datasets.
- **Session auto-save** to `session.json` in the loaded folder (or next to a single loaded image) when you switch images, save manually, or quit—so annotations are harder to lose mid-session.

## Requirements

- Python 3.8+
- See `requirements.txt` for packages.

## Installation

```bash
cd annotation_tool
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Quick workflow

1. **Load Folder** (or **Load Image**).
2. Type class names in the right panel and press **Enter** to add them; click a class to set it as active (or use number keys **1–9**).
3. Click and drag on the image to create a box. Click a box to select it; drag the **white corner squares** to resize.
4. Use **Previous** / **Next** or the list to move between images.
5. Choose export **size**, **format**, and whether to include **cropped patches**, then **Export…** (all loaded images) or press **E** for the **current image only**.

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| **A** / **D** | Previous / next image |
| **Delete** | Delete selected box |
| **S** | Save session (`session.json`) |
| **E** | Export current image only (pick output folder) |
| **Ctrl+Z** (⌘Z on macOS) | Undo last box added on the current image |
| **1**–**9** | Select class by position in the list |

## Export formats

| Format | Output |
|--------|--------|
| **YOLO** | One `.txt` per image: `class_id center_x center_y width height` (0–1 normalized), plus `classes.txt` listing class names in order. |
| **Pascal VOC** | One `.xml` per image with image size and each object’s pixel bounding box. |
| **CSV** | One `.csv` per image with columns `filename`, `x1`, `y1`, `x2`, `y2`, `class`. |

If **Export cropped patches** is enabled, crops are written under `crops/` in the export directory as `classname_imagename_index.jpg`, resized to the chosen square size.

## Project layout

```
annotation_tool/
├── main.py              # Entry point
├── mainwindow.py        # Main window, session, shortcuts
├── canvas.py            # Image view, boxes, selection, resize handles
├── sidebar_left.py      # Load & image list
├── sidebar_right.py     # Classes & export controls
├── annotation.py        # BoundingBox, ImageAnnotation
├── exporter.py          # YOLO / VOC / CSV / crops
├── utils.py             # Layout helpers
├── requirements.txt
└── assets/icons/        # Optional icons
```

## License

Add a `LICENSE` file if you distribute this project publicly.
