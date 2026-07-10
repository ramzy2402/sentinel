from abc import ABC, abstractmethod
from PIL import Image

class OCREngine(ABC):
    @abstractmethod
    def extract_text(self, image: Image.Image) -> str: ...

class EasyOCREngine(OCREngine):
    def __init__(self, languages=None, use_gpu: bool = True):
        import easyocr
        self._reader = easyocr.Reader(languages or ["fr", "en"], gpu=use_gpu)

    def extract_text(self, image: Image.Image) -> str:
        import numpy as np
        results = self._reader.readtext(np.array(image), detail=0)
        return "\n".join(results)

class PyTesseractEngine(OCREngine):
    def __init__(self):
        import pytesseract
        pass # Vérifie que tesseract est bien installé sur ton système

    def extract_text(self, image: Image.Image) -> str:
        import pytesseract
        return pytesseract.image_to_string(image, lang="fra+eng")