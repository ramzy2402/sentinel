import time
from pathlib import Path
from backend.memory.encryption import encrypt

LOG_FILE = Path("state/activity.log.enc")

def log_event(message: str):
    try:
        line = f"{time.time()}|{message}"
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(encrypt(line) + "\n")
    except Exception as e:
        print(f"[Sentinel] Erreur de journalisation (non bloquante) : {e}")