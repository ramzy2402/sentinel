"""
Raccourci clavier global qui stoppe INSTANTANÉMENT toute action en
cours de l'agent, peu importe le module qui l'exécute.
"""
import threading
import keyboard

ABORT_SIGNAL = threading.Event()


def _trigger_panic():
    print("[Sentinel] PANIC BUTTON ACTIVÉ - arrêt immédiat de toutes les actions.")
    ABORT_SIGNAL.set()


def start_panic_listener(hotkey: str = "ctrl+shift+esc"):
    keyboard.add_hotkey(hotkey, _trigger_panic)


def reset_panic():
    ABORT_SIGNAL.clear()


def check_abort():
    """À appeler avant CHAQUE étape d'une action automatisée."""
    if ABORT_SIGNAL.is_set():
        raise RuntimeError("Action interrompue par le bouton panique.")
