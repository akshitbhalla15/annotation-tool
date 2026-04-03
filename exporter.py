import csv
import os
import re
import xml.etree.ElementTree as ET
from typing import List, Optional

from PIL import Image

from annotation import BoundingBox, ImageAnnotation


def _safe_name(s: str) -> str:
    return re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE)


def export_classes_file(classes: List[str], out_dir: str) -> str:
    path = os.path.join(out_dir, "classes.txt")
    with open(path, "w", encoding="utf-8") as f:
        for c in classes:
            f.write(c + "\n")
    return path


def _yolo_line(
    box: BoundingBox, class_id: int, img_w: int, img_h: int
) -> str:
    x1, y1, x2, y2 = box.normalized()
    bw = x2 - x1
    bh = y2 - y1
    cx = (x1 + x2) / 2.0 / img_w
    cy = (y1 + y2) / 2.0 / img_h
    nw = bw / img_w
    nh = bh / img_h
    return f"{class_id} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}"


def export_yolo_for_image(
    ann: ImageAnnotation,
    classes: List[str],
    out_dir: str,
    write_classes_txt: bool = True,
) -> Optional[str]:
    if not ann.image_path or not os.path.isfile(ann.image_path):
        return None
    os.makedirs(out_dir, exist_ok=True)
    if write_classes_txt:
        export_classes_file(classes, out_dir)
    base = os.path.splitext(os.path.basename(ann.image_path))[0]
    txt_path = os.path.join(out_dir, base + ".txt")
    with Image.open(ann.image_path) as im:
        iw, ih = im.size
    class_to_id = {c: i for i, c in enumerate(classes)}
    lines = []
    for b in ann.boxes:
        if b.label not in class_to_id:
            continue
        lines.append(_yolo_line(b, class_to_id[b.label], iw, ih))
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        if lines:
            f.write("\n")
    return txt_path


def export_voc_for_image(ann: ImageAnnotation, out_dir: str) -> Optional[str]:
    if not ann.image_path or not os.path.isfile(ann.image_path):
        return None
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(ann.image_path))[0]
    xml_path = os.path.join(out_dir, base + ".xml")
    with Image.open(ann.image_path) as im:
        iw, ih = im.size
        depth = len(im.getbands())

    root = ET.Element("annotation")
    ET.SubElement(root, "folder").text = os.path.basename(
        os.path.dirname(ann.image_path)
    )
    ET.SubElement(root, "filename").text = os.path.basename(ann.image_path)
    ET.SubElement(root, "path").text = ann.image_path
    source = ET.SubElement(root, "source")
    ET.SubElement(source, "database").text = "Unknown"
    size_el = ET.SubElement(root, "size")
    ET.SubElement(size_el, "width").text = str(iw)
    ET.SubElement(size_el, "height").text = str(ih)
    ET.SubElement(size_el, "depth").text = str(depth)
    ET.SubElement(root, "segmented").text = "0"

    for b in ann.boxes:
        x1, y1, x2, y2 = b.normalized()
        obj = ET.SubElement(root, "object")
        ET.SubElement(obj, "name").text = b.label
        ET.SubElement(obj, "pose").text = "Unspecified"
        ET.SubElement(obj, "truncated").text = "0"
        ET.SubElement(obj, "difficult").text = "0"
        bb = ET.SubElement(obj, "bndbox")
        ET.SubElement(bb, "xmin").text = str(int(x1))
        ET.SubElement(bb, "ymin").text = str(int(y1))
        ET.SubElement(bb, "xmax").text = str(int(x2))
        ET.SubElement(bb, "ymax").text = str(int(y2))

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(xml_path, encoding="unicode", xml_declaration=True)
    return xml_path


def export_csv_for_image(ann: ImageAnnotation, out_dir: str) -> Optional[str]:
    if not ann.image_path or not os.path.isfile(ann.image_path):
        return None
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(ann.image_path))[0]
    csv_path = os.path.join(out_dir, base + ".csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["filename", "x1", "y1", "x2", "y2", "class"])
        name = os.path.basename(ann.image_path)
        for b in ann.boxes:
            x1, y1, x2, y2 = b.normalized()
            w.writerow([name, int(x1), int(y1), int(x2), int(y2), b.label])
    return csv_path


def export_crops_for_image(
    ann: ImageAnnotation,
    out_dir: str,
    size: int,
) -> int:
    if not ann.image_path or not os.path.isfile(ann.image_path):
        return 0
    os.makedirs(out_dir, exist_ok=True)
    img_base = os.path.splitext(os.path.basename(ann.image_path))[0]
    img_base_safe = _safe_name(img_base)
    count = 0
    with Image.open(ann.image_path).convert("RGB") as im:
        for idx, b in enumerate(ann.boxes):
            x1, y1, x2, y2 = b.normalized()
            x1, y1 = max(0, int(x1)), max(0, int(y1))
            x2, y2 = min(im.width, int(x2)), min(im.height, int(y2))
            if x2 <= x1 or y2 <= y1:
                continue
            crop = im.crop((x1, y1, x2, y2))
            try:
                resample = Image.Resampling.LANCZOS
            except AttributeError:
                resample = Image.LANCZOS
            crop = crop.resize((size, size), resample)
            cls = _safe_name(b.label) or "object"
            out_name = f"{cls}_{img_base_safe}_{idx}.jpg"
            crop.save(os.path.join(out_dir, out_name), quality=92)
            count += 1
    return count


def export_batch(
    annotations: List[ImageAnnotation],
    classes: List[str],
    out_dir: str,
    format_name: str,
    crop_mode: bool,
    crop_size: int,
) -> None:
    """
    format_name: 'yolo' | 'voc' | 'csv'
    If crop_mode, also writes crops to out_dir/crops/
    """
    os.makedirs(out_dir, exist_ok=True)
    first_yolo = True
    for ann in annotations:
        if crop_mode:
            cdir = os.path.join(out_dir, "crops")
            export_crops_for_image(ann, cdir, crop_size)
        if format_name == "yolo":
            export_yolo_for_image(
                ann, classes, out_dir, write_classes_txt=first_yolo
            )
            first_yolo = False
        elif format_name == "voc":
            export_voc_for_image(ann, out_dir)
        elif format_name == "csv":
            export_csv_for_image(ann, out_dir)
