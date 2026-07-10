import json
import time
from pathlib import Path

STATE_DIR = Path("state")
STATE_DIR.mkdir(exist_ok=True)

STATUS_FILE = STATE_DIR / "status.json"
PANIC_FLAG = STATE_DIR / "panic.flag"

def write_status(phase: str, detail: str = ""):
    try:
        STATUS_FILE.write_text(json.dumps({
            "phase": phase,
            "detail": detail,
            "updated_at": time.time(),
        }, ensure_ascii=False))
    except Exception as e:
        print(f"[Sentinel] Impossible d'écrire le statut : {e}")

def read_status() -> dict:
    if not STATUS_FILE.exists():
        return {"phase": "veille", "detail": "Non démarré", "updated_at": time.time()}
    try:
        return json.loads(STATUS_FILE.read_text())
    except Exception:
        return {"phase": "erreur", "detail": "Lecture du statut impossible", "updated_at": time.time()}

def trigger_panic_flag():
    PANIC_FLAG.touch()

def clear_panic_flag():
    if PANIC_FLAG.exists():
        PANIC_FLAG.unlink()

def is_panicked() -> bool:
    return PANIC_FLAG.exists()