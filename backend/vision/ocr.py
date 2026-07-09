"""
Extraction de texte via RapidOCR (léger, rapide, local).
"""
from dataclasses import dataclass
from typing import List

from rapidocr_onnxruntime import RapidOCR
from PIL import Image
import numpy as np

_engine = RapidOCR()


@dataclass
class TextBlock:
    text: str
    confidence: float
    bbox: list


def extract_text(image: Image.Image) -> List[TextBlock]:
    result, _ = _engine(np.array(image))
    if not result:
        return []
    return [TextBlock(text=r[1], confidence=float(r[2]), bbox=r[0]) for r in result]


def full_text(image: Image.Image) -> str:
    blocks = extract_text(image)
    return "\n".join(b.text for b in blocks)
