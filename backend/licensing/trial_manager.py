"""
Gère la logique d'essai 30 jours : 15 jours d'observation passive
(aucune action exécutée, uniquement mémorisée), puis 15 jours de
déploiement (suggestions actives).
"""
import time
from pathlib import Path

TRIAL_START_FILE = Path("trial_start.txt")
OBSERVATION_DAYS = 15
TOTAL_TRIAL_DAYS = 30


def get_trial_phase() -> str:
    if not TRIAL_START_FILE.exists():
        TRIAL_START_FILE.write_text(str(time.time()))
        return "observation"

    start = float(TRIAL_START_FILE.read_text())
    days_elapsed = (time.time() - start) / 86400

    if days_elapsed < OBSERVATION_DAYS:
        return "observation"
    elif days_elapsed < TOTAL_TRIAL_DAYS:
        return "deployment"
    else:
        return "expired"
