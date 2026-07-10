print("BACKEND_READY")
"""
Orchestrateur principal de Sentinel.
"""
from backend.benchmark import run_benchmark, CONFIG_PATH
from backend.vision.capture import ScreenWatcher, Frame
from backend.vision.ocr_engine import EasyOCREngine
from backend.state.status_store import write_status, is_panicked
from backend.security.secure_logger import log_event

# Initialisation du moteur OCR
ocr_engine = EasyOCREngine()

def safe_step(step_name: str, func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        log_event(f"Erreur dans l'étape '{step_name}' : {e}")
        write_status("erreur", detail=f"{step_name} a échoué, reprise automatique")
        return None

def on_change(frame: Frame):
    if is_panicked():
        write_status("pause", detail="Bouton panique actif")
        return

    write_status("observation", detail=f"Analyse de : {frame.window_title}")

    text = safe_step("ocr", ocr_engine.extract_text, frame.image)
    if not text or not text.strip():
        return

    safe_step("log", log_event, f"Texte observé dans {frame.window_title}")

def run_persistent_loop():
    write_status("veille", detail="Démarrage de Sentinel")

    if not CONFIG_PATH.exists():
        safe_step("benchmark", run_benchmark)

    watcher = ScreenWatcher(interval=2.0)
    write_status("observation", detail="Surveillance d'écran active")

    try:
        watcher.watch(on_change)
    except Exception as e:
        log_event(f"Erreur fatale de la boucle principale : {e}")
        write_status("erreur", detail="La boucle principale s'est arrêtée")

if __name__ == "__main__":
    import argparse
    import json
    from backend.state.status_store import read_status, trigger_panic_flag, clear_panic_flag

    parser = argparse.ArgumentParser()
    parser.add_argument("--message", type=str, default=None)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--panic", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args, _ = parser.parse_known_args()

    if args.message is not None:
        print(f"Hello from Python, tu as envoyé : {args.message}")
    elif args.status:
        print(json.dumps(read_status(), ensure_ascii=False))
    elif args.panic:
        trigger_panic_flag()
        print(json.dumps({"ok": True, "phase": "pause"}, ensure_ascii=False))
    elif args.resume:
        clear_panic_flag()
        print(json.dumps({"ok": True, "phase": "veille"}, ensure_ascii=False))
    else:
        run_persistent_loop()