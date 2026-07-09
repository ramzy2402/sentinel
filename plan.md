# Sentinel — Plan de développement technique complet

> Assistant IA agentique local pour Gestionnaires de Patrimoine / CIF
> Ce document couvre l'architecture, l'arborescence du projet, et le code de démarrage pour chaque module, dans l'ordre où tu dois les construire.

---

## Sommaire

1. [Choix techniques et pourquoi ils sont les plus performants](#1-choix-techniques)
2. [Arborescence du projet](#2-arborescence)
3. [Phase 0 — Setup environnement](#phase-0)
4. [Phase 1 — Script de Benchmark](#phase-1)
5. [Phase 2 — Module Vision](#phase-2)
6. [Phase 3 — Module Sécurité](#phase-3)
7. [Phase 4 — Mémoire contextuelle](#phase-4)
8. [Phase 5 — Module Action](#phase-5)
9. [Phase 6 — Intelligence de décision (LangGraph)](#phase-6)
10. [Phase 7 — Pont API vers Tauri](#phase-7)
11. [Phase 8 — Assemblage (main.py)](#phase-8)
12. [Phase 9 — Interface Tauri](#phase-9)
13. [Phase 10 — Gestion de l'essai / licence](#phase-10)
14. [Phase 11 — Packaging & distribution](#phase-11)
15. [Roadmap semaine par semaine](#15-roadmap)
16. [Prochaines étapes immédiates](#16-prochaines-etapes)

---

<a id="1-choix-techniques"></a>
## 1. Choix techniques et pourquoi ils sont les plus performants

| Besoin | Choix | Pourquoi |
|---|---|---|
| Shell UI | **Tauri** (Rust) | 5-10x plus léger qu'Electron, démarrage quasi instantané, empreinte mémoire minimale — critique pour un outil qui tourne en fond toute la journée |
| Inférence LLM | **Ollama** local | Tu as déjà `qwen3:8b` installé avec Goose — on le réutilise directement, pas de nouvelle install |
| Sélection de modèle | Benchmark matériel au 1er lancement | Ta RTX 5060 permet de faire tourner un modèle 8B correctement ; le script détecte ça automatiquement plutôt que de forcer un choix unique |
| Capture d'écran | **mss** + hash perceptuel (imagehash) | On ne traite JAMAIS une frame identique à la précédente → énorme économie CPU/GPU sur une capture en continu |
| OCR | **RapidOCR** (ONNX) | Rapide, tourne bien même sans GPU dédié à l'OCR, pas de dépendance cloud |
| Automatisation Windows | **pywinauto** plutôt que PyAutoGUI | Cible les éléments d'UI réels (boutons, champs), pas des coordonnées pixel qui cassent au moindre changement de résolution/fenêtre |
| Automatisation navigateur | **Playwright** | Plus stable et plus rapide que Selenium |
| Mémoire vectorielle | **ChromaDB** local persistant | Pas de service cloud, requêtes de similarité rapides même avec des dizaines de milliers d'entrées |
| Orchestration | **LangGraph** | Modélise la boucle Observer → Décider → Agir comme un graphe d'états explicite, plus robuste qu'une chaîne de prompts |
| Sécurité anti-hallucination | **Whitelist d'actions** | Le LLM ne peut JAMAIS déclencher une action qui n'existe pas dans un registre validé par toi — point commun avec toute IA qui agit sur des systèmes réels |

---

<a id="2-arborescence"></a>
## 2. Arborescence du projet

```
sentinel/
├── src-tauri/
│   ├── src/
│   ├── binaries/                  <- le .exe Python compilé va ici
│   └── tauri.conf.json
├── frontend/
│   └── src/App.tsx
├── backend/
│   ├── benchmark.py
│   ├── vision/
│   │   ├── capture.py
│   │   └── ocr.py
│   ├── security/
│   │   ├── anonymizer.py
│   │   └── panic_button.py
│   ├── memory/
│   │   ├── encryption.py
│   │   └── vector_store.py
│   ├── actions/
│   │   ├── desktop_actions.py
│   │   └── browser_actions.py
│   ├── orchestrator/
│   │   └── graph.py
│   ├── api/
│   │   └── server.py
│   ├── licensing/
│   │   └── trial_manager.py
│   ├── main.py
│   └── requirements.txt
└── installer/
```

---

<a id="phase-0"></a>
## Phase 0 — Setup environnement

```bash
# 1. Ollama (déjà fait chez toi, on ajoute juste le modèle d'embedding)
ollama pull nomic-embed-text

# 2. Environnement Python
python -m venv venv
venv\Scripts\activate
pip install -r backend/requirements.txt
python -m spacy download fr_core_news_sm
playwright install chromium

# 3. Tauri
npm create tauri-app@latest frontend
cd frontend
npm install
```

`backend/requirements.txt` :

```
fastapi
uvicorn[standard]
websockets
psutil
pynvml
mss
Pillow
imagehash
rapidocr-onnxruntime
chromadb
ollama
langgraph
langchain-core
pywinauto
playwright
pygetwindow
pywin32
keyboard
cryptography
presidio-analyzer
presidio-anonymizer
pyinstaller
```

---

<a id="phase-1"></a>
## Phase 1 — Script de Benchmark

`backend/benchmark.py`

```python
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
```

Avec ta RTX 5060, ce script choisira automatiquement `qwen3:8b` (déjà installé) — pas de téléchargement inutile.

---

<a id="phase-2"></a>
## Phase 2 — Module Vision

`backend/vision/capture.py`

```python
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
```

`backend/vision/ocr.py`

```python
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
```

---

<a id="phase-3"></a>
## Phase 3 — Module Sécurité

`backend/memory/encryption.py` (mise ici car utilisée par la mémoire, mais logiquement liée à la sécurité)

```python
"""
Chiffrement des données sensibles au repos. La clé maîtresse est
protégée par la DPAPI de Windows (liée au compte utilisateur Windows).
"""
from pathlib import Path
from cryptography.fernet import Fernet

try:
    import win32crypt
    HAS_DPAPI = True
except Exception:
    HAS_DPAPI = False

KEY_FILE = Path("sentinel.key")


def _protect(data: bytes) -> bytes:
    if HAS_DPAPI:
        return win32crypt.CryptProtectData(data, "SentinelKey", None, None, None, 0)
    return data


def _unprotect(data: bytes) -> bytes:
    if HAS_DPAPI:
        return win32crypt.CryptUnprotectData(data, None, None, None, 0)[1]
    return data


def load_or_create_key() -> bytes:
    if KEY_FILE.exists():
        return _unprotect(KEY_FILE.read_bytes())
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(_protect(key))
    return key


_fernet = Fernet(load_or_create_key())


def encrypt(text: str) -> str:
    return _fernet.encrypt(text.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    return _fernet.decrypt(token.encode("utf-8")).decode("utf-8")
```

`backend/security/anonymizer.py`

```python
"""
Détecte et masque les données personnelles (noms, IBAN, emails,
téléphones) AVANT tout passage en mémoire vectorielle ou au LLM.
Défense en profondeur : même en local, un cabinet CIF manipule des
données patrimoniales ultra-sensibles.
"""
import re
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

_nlp_config = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "fr", "model_name": "fr_core_news_sm"}],
}
_provider = NlpEngineProvider(nlp_configuration=_nlp_config)
_nlp_engine = _provider.create_engine()

_analyzer = AnalyzerEngine(nlp_engine=_nlp_engine, supported_languages=["fr"])
_anonymizer = AnonymizerEngine()

IBAN_REGEX = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")


def anonymize(text: str) -> str:
    text = IBAN_REGEX.sub("[IBAN_MASQUÉ]", text)
    results = _analyzer.analyze(text=text, language="fr")
    anonymized = _anonymizer.anonymize(text=text, analyzer_results=results)
    return anonymized.text
```

`backend/security/panic_button.py`

```python
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
```

---

<a id="phase-4"></a>
## Phase 4 — Mémoire contextuelle

`backend/memory/vector_store.py`

```python
"""
Mémoire contextuelle vectorielle locale (ChromaDB), champs sensibles
chiffrés avant stockage.
"""
import time
import uuid
import ollama
import chromadb

from backend.memory.encryption import encrypt, decrypt

_client = chromadb.PersistentClient(path="./sentinel_memory")
_collection = _client.get_or_create_collection("work_context")


def embed(text: str, model: str = "nomic-embed-text") -> list:
    response = ollama.embeddings(model=model, prompt=text)
    return response["embedding"]


def store_event(text: str, window_title: str, event_type: str = "observation"):
    vector = embed(text)
    doc_id = str(uuid.uuid4())
    _collection.add(
        ids=[doc_id],
        embeddings=[vector],
        documents=[encrypt(text)],
        metadatas=[{
            "window_title": window_title,
            "event_type": event_type,
            "timestamp": time.time(),
        }],
    )
    return doc_id


def query_similar(text: str, n_results: int = 5) -> list:
    vector = embed(text)
    results = _collection.query(query_embeddings=[vector], n_results=n_results)
    docs = results.get("documents", [[]])[0]
    return [decrypt(d) for d in docs]
```

---

<a id="phase-5"></a>
## Phase 5 — Module Action

`backend/actions/desktop_actions.py`

```python
"""
Exécution d'actions sur des applications Windows via pywinauto (cible
les éléments d'UI réels, pas des coordonnées pixel fixes).

Le ACTION_WHITELIST est le garde-fou anti-hallucination central :
le LLM ne peut JAMAIS déclencher une action qui n'y figure pas.
"""
from pywinauto import Application
from backend.security.panic_button import check_abort

ACTION_WHITELIST = {}


def register_action(name: str):
    def decorator(func):
        ACTION_WHITELIST[name] = func
        return func
    return decorator


def execute_action(name: str, **kwargs):
    check_abort()
    if name not in ACTION_WHITELIST:
        raise ValueError(f"Action '{name}' inconnue - exécution refusée.")
    return ACTION_WHITELIST[name](**kwargs)


@register_action("open_app_and_focus")
def open_app_and_focus(path: str):
    check_abort()
    app = Application(backend="uia").start(path)
    return app


@register_action("type_text_in_field")
def type_text_in_field(window_title: str, control_name: str, text: str):
    check_abort()
    app = Application(backend="uia").connect(title_re=window_title)
    win = app.window(title_re=window_title)
    win[control_name].type_keys(text, with_spaces=True)
```

`backend/actions/browser_actions.py`

```python
"""
Automatisation navigateur via Playwright, même logique de whitelist
et de vérification panique que pour les actions desktop.
"""
from playwright.sync_api import sync_playwright
from backend.security.panic_button import check_abort
from backend.actions.desktop_actions import register_action

_playwright = None
_browser = None


def get_browser():
    global _playwright, _browser
    if _browser is None:
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=False)
    return _browser


@register_action("fill_web_form")
def fill_web_form(url: str, fields: dict):
    check_abort()
    browser = get_browser()
    page = browser.new_page()
    page.goto(url)
    for selector, value in fields.items():
        check_abort()
        page.fill(selector, value)
    return page
```

---

<a id="phase-6"></a>
## Phase 6 — Intelligence de décision (LangGraph)

`backend/orchestrator/graph.py`

```python
"""
Cerveau décisionnel de Sentinel.
Boucle : Anonymiser -> Retrouver contexte -> Décider -> Proposer/Exécuter -> Mémoriser
"""
import json
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
import ollama

from backend.memory.vector_store import store_event, query_similar
from backend.actions.desktop_actions import ACTION_WHITELIST
from backend.security.anonymizer import anonymize


class SentinelState(TypedDict):
    raw_text: str
    window_title: str
    anonymized_text: str
    similar_context: list
    decision: Optional[dict]
    trial_phase: str  # "observation" ou "deployment"


def node_anonymize(state: SentinelState) -> SentinelState:
    state["anonymized_text"] = anonymize(state["raw_text"])
    return state


def node_retrieve_memory(state: SentinelState) -> SentinelState:
    state["similar_context"] = query_similar(state["anonymized_text"])
    return state


def node_decide(state: SentinelState) -> SentinelState:
    available_actions = ", ".join(ACTION_WHITELIST.keys())
    prompt = f"""Tu es Sentinel, un assistant qui observe le travail d'un
professionnel. Voici ce qui vient de se passer à l'écran :
"{state['anonymized_text']}"

Contexte similaire déjà observé : {state['similar_context']}

Actions que tu as le droit de proposer (UNIQUEMENT celles-ci, aucune autre) :
{available_actions}

Si tu identifies un pattern répétitif clair, réponds en JSON strict :
{{"suggest_action": "<nom_action_de_la_liste_ou_null>", "reason": "<courte explication>"}}
Sinon réponds {{"suggest_action": null, "reason": "observation seule"}}
"""
    response = ollama.chat(
        model="qwen3:8b",
        messages=[{"role": "user", "content": prompt}],
        format="json",
    )
    state["decision"] = json.loads(response["message"]["content"])
    return state


def node_act_or_suggest(state: SentinelState) -> SentinelState:
    decision = state["decision"]
    action_name = decision.get("suggest_action")

    # Deuxième vérification : même si le LLM invente un nom d'action,
    # on ne fait confiance qu'au registre whitelist réel.
    if action_name and action_name in ACTION_WHITELIST:
        if state["trial_phase"] == "observation":
            print(f"[Sentinel] (mode observation) suggestion ignorée : {action_name}")
        else:
            print(f"[Sentinel] Suggestion à valider par l'utilisateur : {action_name}")
            # -> envoyer l'événement au frontend Tauri via WebSocket
            # pour demander confirmation humaine avant exécution réelle.
    return state


def node_memorize(state: SentinelState) -> SentinelState:
    store_event(state["anonymized_text"], state["window_title"])
    return state


def build_graph():
    graph = StateGraph(SentinelState)
    graph.add_node("anonymize", node_anonymize)
    graph.add_node("retrieve_memory", node_retrieve_memory)
    graph.add_node("decide", node_decide)
    graph.add_node("act_or_suggest", node_act_or_suggest)
    graph.add_node("memorize", node_memorize)

    graph.set_entry_point("anonymize")
    graph.add_edge("anonymize", "retrieve_memory")
    graph.add_edge("retrieve_memory", "decide")
    graph.add_edge("decide", "act_or_suggest")
    graph.add_edge("act_or_suggest", "memorize")
    graph.add_edge("memorize", END)

    return graph.compile()
```

Remarque : rien ici n'exécute jamais une action inventée par le modèle. `act_or_suggest` ne fait que proposer, et l'exécution réelle passe toujours par `execute_action()` du module Action, après confirmation humaine en phase "deployment".

---

<a id="phase-7"></a>
## Phase 7 — Pont API vers Tauri

`backend/api/server.py`

```python
"""
Pont entre le moteur Python et l'interface Tauri, via WebSocket sur
localhost uniquement (aucune exposition réseau externe).
"""
import json
from fastapi import FastAPI, WebSocket
import uvicorn

app = FastAPI()
connected_clients: list[WebSocket] = []


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        connected_clients.remove(websocket)


async def broadcast_event(event: dict):
    payload = json.dumps(event, ensure_ascii=False)
    for client in connected_clients:
        await client.send_text(payload)


def start_server():
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
```

---

<a id="phase-8"></a>
## Phase 8 — Assemblage (main.py)

`backend/main.py`

```python
"""
Point d'entrée principal : benchmark si nécessaire, watcher d'écran,
bouton panique, et API vers Tauri, tous démarrés ensemble.
"""
import threading
import time
from pathlib import Path

from backend.benchmark import run_benchmark, CONFIG_PATH
from backend.vision.capture import ScreenWatcher, Frame
from backend.vision.ocr import full_text
from backend.security.panic_button import start_panic_listener
from backend.orchestrator.graph import build_graph
from backend.api.server import start_server
from backend.licensing.trial_manager import get_trial_phase


def main():
    if not CONFIG_PATH.exists():
        run_benchmark()

    start_panic_listener()

    api_thread = threading.Thread(target=start_server, daemon=True)
    api_thread.start()

    graph = build_graph()
    watcher = ScreenWatcher(interval=2.0)

    def on_change(frame: Frame):
        text = full_text(frame.image)
        if not text.strip():
            return
        graph.invoke({
            "raw_text": text,
            "window_title": frame.window_title,
            "trial_phase": get_trial_phase(),
        })

    print("[Sentinel] Démarrage de la surveillance d'écran...")
    watcher.watch(on_change)


if __name__ == "__main__":
    main()
```

---

<a id="phase-9"></a>
## Phase 9 — Interface Tauri

`src-tauri/tauri.conf.json` (extrait — configure le backend Python comme sidecar)

```json
{
  "tauri": {
    "bundle": {
      "externalBin": ["binaries/sentinel-backend"]
    }
  }
}
```

`frontend/src/App.tsx` (extrait)

```tsx
import { useEffect, useState } from "react";

export default function App() {
  const [suggestion, setSuggestion] = useState<string | null>(null);

  useEffect(() => {
    const ws = new WebSocket("ws://127.0.0.1:8765/ws");
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "suggestion") {
        setSuggestion(data.reason);
      }
    };
    return () => ws.close();
  }, []);

  return (
    <div className="app">
      {suggestion && (
        <div className="suggestion-banner">
          <p>{suggestion}</p>
          <button>Automatiser</button>
          <button>Ignorer</button>
        </div>
      )}
    </div>
  );
}
```

---

<a id="phase-10"></a>
## Phase 10 — Gestion de l'essai / licence

`backend/licensing/trial_manager.py`

```python
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
```

Pour la version commerciale, ce module devra vérifier une licence signée (ex. JWT) récupérée une fois auprès d'un petit serveur cloud — c'est le seul point de contact réseau externe de tout le logiciel, tout le reste reste 100% local.

---

<a id="phase-11"></a>
## Phase 11 — Packaging & distribution

```bash
# 1. Compiler le backend Python en exécutable autonome
pyinstaller --onefile --name sentinel-backend backend/main.py

# 2. Placer le binaire dans src-tauri/binaries/ avec le suffixe
#    de la cible (ex: sentinel-backend-x86_64-pc-windows-msvc.exe)
#    conformément à la convention de nommage des sidecars Tauri

# 3. Builder l'installeur final
cd frontend
npm run tauri build
```

Le résultat est un `.msi` unique que le client installe sans avoir Python ni Ollama préinstallés manuellement — le premier lancement peut déclencher l'installation d'Ollama silencieusement si besoin.

---

<a id="15-roadmap"></a>
## 15. Roadmap semaine par semaine

| Semaine | Objectif |
|---|---|
| 1 | Setup complet + Benchmark + Capture d'écran (Phases 0, 1, 2) |
| 2 | OCR + Mémoire vectorielle + chiffrement (Phase 2 suite, 4) |
| 3 | Anonymisation + bouton panique + whitelist d'actions (Phase 3, 5) |
| 4 | Orchestrateur LangGraph + tests de la boucle de décision (Phase 6) |
| 5 | Actions desktop (pywinauto) + navigateur (Playwright) réelles (Phase 5 suite) |
| 6 | Interface Tauri + bridge WebSocket + UI de suggestion (Phase 7, 9) |
| 7 | Gestion essai/licence + packaging PyInstaller + installeur (Phase 10, 11) |
| 8 | Tests terrain avec un vrai gestionnaire de patrimoine, itérations |

---

<a id="16-prochaines-etapes"></a>
## 16. Prochaines étapes immédiates

1. Crée le dossier `sentinel/` avec l'arborescence ci-dessus.
2. Lance les commandes de la Phase 0 (venv, requirements, spacy, playwright, tauri).
3. Colle le code de `benchmark.py` et exécute-le seul (`python -m backend.benchmark`) pour vérifier qu'il détecte bien ta RTX 5060 et choisit `qwen3:8b`.
4. Construis et teste `vision/capture.py` + `vision/ocr.py` isolément : lance juste le watcher et affiche le texte extrait dans la console, sans rien connecter d'autre.
5. Une fois la vision validée, ajoute la mémoire (Phase 4), puis la sécurité (Phase 3).
6. Ne branche l'orchestrateur LangGraph qu'en dernier, une fois que chaque brique fonctionne indépendamment — c'est plus facile à déboguer module par module qu'à tout construire d'un bloc.

---

**Note importante** : ce document te donne une architecture complète et du code fonctionnel de démarrage pour chaque module, mais pas un produit fini clé en main — c'est un projet de plusieurs semaines. Chaque script devra être renforcé (gestion d'erreurs, cas limites, tests) au fur et à mesure que tu avances.
