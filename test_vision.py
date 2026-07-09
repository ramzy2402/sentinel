from backend.vision.capture import ScreenWatcher, Frame
from backend.vision.ocr import full_text

def on_change(frame: Frame):
    print(f"[Test] Changement détecté dans : {frame.window_title}")
    text = full_text(frame.image)
    print(f"[Test] Texte extrait :\n{text[:200]}...")

if __name__ == "__main__":
    print("[Test] Démarrage du watcher (appuyez sur Ctrl+C pour arrêter)...")
    watcher = ScreenWatcher(interval=5.0)
    try:
        watcher.watch(on_change)
    except KeyboardInterrupt:
        watcher.stop()
        print("[Test] Arrêt.")
