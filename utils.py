from typing import Tuple


def fit_size(
    orig_w: int, orig_h: int, max_w: int, max_h: int
) -> Tuple[int, int]:
    """Scale (orig_w, orig_h) to fit inside (max_w, max_h), keep aspect ratio."""
    if orig_w <= 0 or orig_h <= 0:
        return 0, 0
    scale = min(max_w / orig_w, max_h / orig_h)
    dw = int(round(orig_w * scale))
    dh = int(round(orig_h * scale))
    return max(1, dw), max(1, dh)


def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))
