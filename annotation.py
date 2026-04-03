from dataclasses import dataclass, field
from typing import List


@dataclass
class BoundingBox:
    x1: int
    y1: int
    x2: int
    y2: int
    label: str

    def normalized(self) -> tuple:
        """Ensure x1<=x2, y1<=y2."""
        return (
            min(self.x1, self.x2),
            min(self.y1, self.y2),
            max(self.x1, self.x2),
            max(self.y1, self.y2),
        )


@dataclass
class ImageAnnotation:
    image_path: str
    boxes: List[BoundingBox] = field(default_factory=list)
