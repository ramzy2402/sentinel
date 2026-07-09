"""
Détecte les capacités matérielles au premier lancement et configure
le modèle Ollama optimal + les paramètres de performance de Sentinel.
"""
import json
import subprocess
import psutil
from pathlib import Path

try:
    import pynvml
    pynvml.nvmlInit()
    HAS_NVIDIA = True
except Exception:
    HAS_NVIDIA = False

CONFIG_PATH = Path("config.json")

# Modèles candidats, du plus léger au plus lourd (noms Ollama)
MODEL_TIERS = [
    {"name": "qwen2.5:3b",  "min_vram_gb": 0,  "min_ram_gb": 8},
    {"name": "qwen3:8b",    "min_vram_gb": 6,  "min_ram_gb": 16},
    {"name": "qwen2.5:14b", "min_vram_gb": 10, "min_ram_gb": 24},
]

EMBED_MODEL = "nomic-embed-text"


def get_gpu_vram_gb() -> float:
    if not HAS_NVIDIA:
        return 0.0
    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    info = pynvml.nvmlDeviceGetMemoryInfo(handle)
    return round(info.total / (1024 ** 3), 1)


def get_ram_gb() -> float:
    return round(psutil.virtual_memory().total / (1024 ** 3), 1)


def pick_model(vram_gb: float, ram_gb: float) -> str:
    chosen = MODEL_TIERS[0]["name"]
    for tier in MODEL_TIERS:
        if vram_gb >= tier["min_vram_gb"] and ram_gb >= tier["min_ram_gb"]:
            chosen = tier["name"]
    return chosen


def ensure_ollama_model(model_name: str) -> None:
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    if model_name not in result.stdout:
        print(f"[Sentinel] Téléchargement de {model_name}...")
        subprocess.run(["ollama", "pull", model_name], check=True)
    else:
        print(f"[Sentinel] Modèle {model_name} déjà disponible.")


def run_benchmark() -> dict:
    vram = get_gpu_vram_gb()
    ram = get_ram_gb()
    cpu_cores = psutil.cpu_count(logical=False)

    model = pick_model(vram, ram)
    ensure_ollama_model(model)
    ensure_ollama_model(EMBED_MODEL)

    config = {
        "hardware": {
            "vram_gb": vram,
            "ram_gb": ram,
            "cpu_cores": cpu_cores,
            "gpu_detected": HAS_NVIDIA,
        },
        "llm_model": model,
        "embedding_model": EMBED_MODEL,
        "screenshot_interval_seconds": 2 if vram >= 6 else 4,
    }
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    print(f"[Sentinel] Configuration écrite : {config}")
    return config


if __name__ == "__main__":
    run_benchmark()
