"""
Capture d'écran performante avec détection de changement (hash
perceptuel) pour éviter de traiter des frames identiques.
"""
import time
import threading
from dataclasses import dataclass

import mss
import imagehash
from PIL import Image


@dataclass
class Frame:
    image: Image.Image
    timestamp: float
    window_title: str


class ScreenWatcher:
    def __init__(self, interval: float = 2.0, hash_threshold: int = 5):
        self.interval = interval
        self.hash_threshold = hash_threshold
        self._last_hash = None
        self._stop_event = threading.Event()
        self._sct = mss.mss()

    def stop(self):
        self._stop_event.set()

    def _get_active_window_title(self) -> str:
        try:
            import win32gui
            return win32gui.GetWindowText(win32gui.GetForegroundWindow())
        except Exception:
            return "unknown"

    def watch(self, on_change_callback):
        """Appelle on_change_callback(Frame) uniquement quand l'écran
        a réellement changé de façon significative."""
        monitor = self._sct.monitors[1]
        while not self._stop_event.is_set():
            raw = self._sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            current_hash = imagehash.phash(img)

            if self._last_hash is None or (current_hash - self._last_hash) > self.hash_threshold:
                self._last_hash = current_hash
                frame = Frame(
                    image=img,
                    timestamp=time.time(),
                    window_title=self._get_active_window_title(),
                )
                on_change_callback(frame)

            time.sleep(self.interval)
