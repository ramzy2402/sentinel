# Sentinel — Architecture de production (interface + orchestrateur)

> Ce document consolide et fait évoluer l'architecture des étapes précédentes vers une version prête pour une mise en production professionnelle. Il s'appuie sur le sidecar déjà fonctionnel (confirmé par ton test "Hello from Python").

---

## 0. Une décision d'architecture importante à connaître avant de lire le code

Le plan initial prévoyait un serveur FastAPI + WebSocket persistant pour la communication frontend/backend. Depuis, on a validé que le pattern `invoke()` + sidecar en mode "one-shot" (`.output()`) fonctionne bien et est plus simple à déboguer. Je consolide donc toute la communication autour de **ce pattern déjà prouvé**, pour une architecture de production plus simple et plus robuste — pas de serveur réseau à gérer, juste des appels ponctuels.

Conséquence technique à comprendre : ton processus d'observation continue (persistant, lancé au démarrage) et tes commandes ponctuelles (`get_status`, `trigger_panic`...) sont **deux processus distincts**. Ils ne peuvent pas partager de mémoire (un `threading.Event` dans l'un n'existe pas dans l'autre). On synchronise donc via de petits fichiers d'état locaux — c'est simple, fiable, et suffisant pour ce cas d'usage.

---

## 1. Structure de fichiers mise à jour

```
sentinel-app/
├── src/
│   ├── index.html
│   ├── main.ts
│   └── styles.css
├── src-tauri/
│   ├── src/lib.rs
│   ├── capabilities/default.json
│   └── tauri.conf.json
├── backend/
│   ├── main.py                        <- orchestrateur principal
│   ├── benchmark.py                   <- inchangé (cf. plan initial)
│   ├── state/
│   │   └── status_store.py            <- NOUVEAU : synchronisation inter-process
│   ├── vision/
│   │   ├── capture.py                 <- inchangé
│   │   └── ocr_engine.py              <- NOUVEAU : interface interchangeable
│   ├── security/
│   │   ├── secure_logger.py           <- NOUVEAU : logs chiffrés
│   │   └── panic_button.py            <- conservé en complément (raccourci local Python)
│   ├── memory/
│   │   ├── encryption.py              <- inchangé (cf. plan initial, phase 4)
│   │   └── context_memory.py          <- NOUVEAU : stub pour ChromaDB plus tard
│   ├── actions/
│   │   └── desktop_actions.py         <- inchangé, whitelist anti-hallucination
│   └── orchestrator/
│       └── llm_client.py              <- NOUVEAU : point d'entrée unique vers Ollama
```

---

## 2. Frontend — `src/index.html`

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <title>Sentinel</title>
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <div class="app">
    <header class="topbar">
      <div class="brand">
        <span class="brand-dot"></span>
        <h1>Sentinel</h1>
      </div>
      <div class="status-badge" id="status-badge" data-phase="veille">
        <span class="status-dot"></span>
        <span id="status-label">Veille</span>
      </div>
      <button id="config-btn" class="icon-btn" title="Configuration">⚙</button>
    </header>

    <main class="content">
      <section class="panel logs-panel">
        <div class="panel-header">
          <h2>Journal d'activité</h2>
          <span class="panel-subtitle">Chiffré localement</span>
        </div>
        <div id="log-list" class="log-list"></div>
      </section>
    </main>

    <footer class="footer">
      <button id="panic-btn" class="panic-btn">Bouton Panique (Ctrl+Shift+Échap)</button>
    </footer>
  </div>

  <script type="module" src="/main.ts"></script>
</body>
</html>
```

## 3. Frontend — `src/styles.css` (dark mode professionnel)

```css
:root {
  --bg-primary: #0b0d12;
  --bg-panel: #12151c;
  --border-subtle: #22262f;
  --text-primary: #e8eaed;
  --text-muted: #8b8f98;
  --accent: #5b8cff;
  --danger: #e5484d;
  --danger-soft: rgba(229, 72, 77, 0.15);
  --warning: #f5a623;
  --radius: 10px;
  --font: -apple-system, "Segoe UI", Inter, sans-serif;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: var(--font);
}

.app { display: flex; flex-direction: column; height: 100vh; }

.topbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-subtle);
}

.brand { display: flex; align-items: center; gap: 8px; flex: 1; }
.brand-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); }
.brand h1 { font-size: 15px; font-weight: 600; margin: 0; letter-spacing: 0.3px; }

.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 999px;
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  font-size: 13px;
}

.status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--text-muted); }
.status-badge[data-phase="observation"] .status-dot { background: var(--accent); }
.status-badge[data-phase="action"] .status-dot { background: var(--warning); }
.status-badge[data-phase="erreur"] .status-dot { background: var(--danger); }
.status-badge[data-phase="pause"] .status-dot { background: var(--warning); }

.icon-btn {
  background: transparent;
  border: 1px solid var(--border-subtle);
  color: var(--text-muted);
  border-radius: var(--radius);
  width: 32px;
  height: 32px;
  cursor: pointer;
}
.icon-btn:hover { color: var(--text-primary); border-color: var(--accent); }

.content { flex: 1; padding: 20px; overflow: hidden; }

.panel {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius);
  height: 100%;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-subtle);
}
.panel-header h2 { font-size: 14px; margin: 0; font-weight: 600; }
.panel-subtitle { font-size: 12px; color: var(--text-muted); }

.log-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px 18px;
  font-family: "SF Mono", "Cascadia Code", monospace;
  font-size: 12.5px;
  color: var(--text-muted);
}
.log-line { padding: 3px 0; }

.footer {
  padding: 16px 20px;
  border-top: 1px solid var(--border-subtle);
  display: flex;
  justify-content: flex-end;
}

.panic-btn {
  background: var(--danger-soft);
  color: var(--danger);
  border: 1px solid var(--danger);
  border-radius: var(--radius);
  padding: 10px 18px;
  font-weight: 600;
  cursor: pointer;
  font-size: 13px;
}
.panic-btn:hover { background: var(--danger); color: white; }
```

## 4. Frontend — `src/main.ts`

```ts
import { invoke } from "@tauri-apps/api/core";

const statusBadge = document.getElementById("status-badge") as HTMLElement;
const statusLabel = document.getElementById("status-label") as HTMLElement;
const logList = document.getElementById("log-list") as HTMLElement;
const panicBtn = document.getElementById("panic-btn") as HTMLButtonElement;
const configBtn = document.getElementById("config-btn") as HTMLButtonElement;

const PHASE_LABELS: Record<string, string> = {
  veille: "Veille",
  observation: "Observation",
  action: "Action",
  pause: "En pause",
  erreur: "Erreur",
};

function addLogLine(text: string) {
  const line = document.createElement("div");
  line.className = "log-line";
  line.textContent = `${new Date().toLocaleTimeString()} — ${text}`;
  logList.prepend(line);
}

async function refreshStatus() {
  try {
    const raw = await invoke<string>("get_status");
    const status = JSON.parse(raw);
    statusBadge.dataset.phase = status.phase;
    statusLabel.textContent = PHASE_LABELS[status.phase] ?? status.phase;
    if (status.detail) addLogLine(status.detail);
  } catch (error) {
    statusBadge.dataset.phase = "erreur";
    statusLabel.textContent = "Erreur";
    addLogLine(`Impossible de contacter le backend : ${error}`);
  }
}

async function triggerPanic() {
  panicBtn.disabled = true;
  try {
    await invoke("trigger_panic");
    addLogLine("Bouton panique activé — toutes les actions sont interrompues.");
  } catch (error) {
    addLogLine(`Erreur lors de l'activation du bouton panique : ${error}`);
  } finally {
    panicBtn.disabled = false;
  }
}

panicBtn.addEventListener("click", triggerPanic);
configBtn.addEventListener("click", () => {
  addLogLine("Ouverture de la configuration (à implémenter)");
});

// Raccourci local : actif seulement quand la fenêtre a le focus.
window.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.shiftKey && e.key === "Escape") triggerPanic();
});

setInterval(refreshStatus, 2000);
refreshStatus();
```

**Note sur le raccourci vraiment global** : le `keydown` ci-dessus ne fonctionne que si la fenêtre Sentinel a le focus. Pour un vrai raccourci système (actif même quand l'utilisateur travaille dans une autre application — ce qui est le vrai besoin pour un bouton panique), ajoute le plugin officiel :

```bash
npm run tauri add global-shortcut
```

Puis dans `main.ts` :

```ts
import { register } from "@tauri-apps/plugin-global-shortcut";

await register("CommandOrControl+Shift+Escape", () => {
  triggerPanic();
});
```

Et ajoute la permission correspondante dans `capabilities/default.json` (`"global-shortcut:allow-register"`).

---

## 5. Rust — ajouts à `src-tauri/src/lib.rs`

En plus de `call_python` déjà en place, ajoute ces trois commandes :

```rust
#[tauri::command]
async fn get_status(app: tauri::AppHandle) -> Result<String, String> {
    let output = app.shell().sidecar("sentinel-backend").map_err(|e| e.to_string())?
        .arg("--status")
        .output().await.map_err(|e| e.to_string())?;
    if output.status.success() {
        Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
    } else {
        Err(String::from_utf8_lossy(&output.stderr).to_string())
    }
}

#[tauri::command]
async fn trigger_panic(app: tauri::AppHandle) -> Result<String, String> {
    let output = app.shell().sidecar("sentinel-backend").map_err(|e| e.to_string())?
        .arg("--panic")
        .output().await.map_err(|e| e.to_string())?;
    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

#[tauri::command]
async fn resume_agent(app: tauri::AppHandle) -> Result<String, String> {
    let output = app.shell().sidecar("sentinel-backend").map_err(|e| e.to_string())?
        .arg("--resume")
        .output().await.map_err(|e| e.to_string())?;
    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}
```

Et mets à jour `invoke_handler` :

```rust
.invoke_handler(tauri::generate_handler![call_python, get_status, trigger_panic, resume_agent])
```

---

## 6. Backend — `backend/state/status_store.py` (nouveau, cœur de la synchronisation)

```python
"""
Synchronisation entre le processus persistant (observation continue)
et les appels ponctuels du frontend. Comme il s'agit de deux processus
séparés, on utilise des fichiers locaux plutôt que de la mémoire
partagée.
"""
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
```

## 7. Backend — `backend/vision/ocr_engine.py` (interface interchangeable)

```python
"""
Interface abstraite pour l'OCR — permet de changer de moteur sans
modifier le reste du code (respecte la contrainte de modularité).
"""
from abc import ABC, abstractmethod
from PIL import Image


class OCREngine(ABC):
    @abstractmethod
    def extract_text(self, image: Image.Image) -> str: ...


class EasyOCREngine(OCREngine):
    """Bonne précision, accélérée par GPU si disponible — profite bien
    de ta RTX 5060. Empreinte disque plus lourde (PyTorch)."""

    def __init__(self, languages=None, use_gpu: bool = True):
        import easyocr
        self._reader = easyocr.Reader(languages or ["fr", "en"], gpu=use_gpu)

    def extract_text(self, image: Image.Image) -> str:
        import numpy as np
        results = self._reader.readtext(np.array(image), detail=0)
        return "\n".join(results)


class PyTesseractEngine(OCREngine):
    """Alternative plus légère (pas de PyTorch), mais nécessite le
    moteur Tesseract installé séparément — packaging plus complexe."""

    def extract_text(self, image: Image.Image) -> str:
        import pytesseract
        return pytesseract.image_to_string(image, lang="fra+eng")
```

## 8. Backend — `backend/security/secure_logger.py`

```python
"""
Logs applicatifs chiffrés au repos, en s'appuyant sur le mécanisme
défini dans memory/encryption.py (Fernet + protection DPAPI Windows).
"""
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
        # Un problème de log ne doit jamais faire planter l'agent
        print(f"[Sentinel] Erreur de journalisation (non bloquante) : {e}")
```

## 9. Backend — `backend/memory/context_memory.py` (stub pour ChromaDB, à brancher plus tard)

```python
"""
Interface prévue pour la mémoire contextuelle. Le reste du code appelle
déjà cette interface — brancher ChromaDB plus tard (cf. plan initial,
phase 4) ne demandera de modifier que ce fichier.
"""
from abc import ABC, abstractmethod


class ContextMemory(ABC):
    @abstractmethod
    def store(self, text: str, metadata: dict) -> None: ...

    @abstractmethod
    def query_similar(self, text: str, n_results: int = 5) -> list: ...


class NoOpMemory(ContextMemory):
    """Implémentation par défaut tant que ChromaDB n'est pas branché."""

    def store(self, text: str, metadata: dict) -> None:
        pass

    def query_similar(self, text: str, n_results: int = 5) -> list:
        return []
```

## 10. Backend — `backend/orchestrator/llm_client.py` (point d'entrée unique vers Ollama)

```python
"""
Point d'entrée UNIQUE vers l'inférence locale. Le reste du code doit
toujours passer par cette fonction plutôt que d'appeler Ollama
directement — ça garantit qu'aucun appel réseau externe ne peut se
glisser ailleurs dans le code (contrainte "local-first").
"""
import ollama

DEFAULT_MODEL = "qwen3:8b"


def ask_local_llm(prompt: str, model: str = DEFAULT_MODEL) -> str:
    try:
        response = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}])
        return response["message"]["content"]
    except Exception as e:
        return f"[Erreur LLM local] {e}"
```

## 11. Backend — `backend/main.py` (orchestrateur principal, mis à jour)

```python
"""
Orchestrateur principal de Sentinel. Chaque étape est isolée par
try/except pour qu'une erreur ponctuelle (OCR raté, capture qui
échoue...) n'interrompe jamais la boucle d'ensemble.
"""
from backend.benchmark import run_benchmark, CONFIG_PATH
from backend.vision.capture import ScreenWatcher, Frame
from backend.vision.ocr_engine import EasyOCREngine
from backend.state.status_store import write_status, is_panicked
from backend.security.secure_logger import log_event

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
    # -> à venir : appel à l'orchestrateur de décision (LangGraph + llm_client)
    #    puis à la mémoire contextuelle (context_memory), cf. plan initial phase 6


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
```

---

## 12. `tauri.conf.json` — points à vérifier pour un packaging propre

- **`bundle.externalBin`** : `["binaries/sentinel-backend"]` (déjà en place).
- **`app.security.csp`** : garde la valeur par défaut de Tauri v2. Comme `index.html` ne charge que des fichiers locaux (`styles.css`, `main.ts` compilé) sans script inline ni CDN externe, tu n'as rien à assouplir — c'est plus sûr ainsi.
- **`app.windows`** : pense à définir un `title: "Sentinel"`, une taille par défaut cohérente avec le dashboard (ex. `"width": 1000, "height": 700`), et éventuellement `"resizable": true`.
- Évite les attributs `onclick="..."` inline dans le HTML (on utilise `addEventListener` dans `main.ts` à la place) — en plus d'être une meilleure pratique, ça reste compatible avec une CSP stricte si tu la resserres plus tard.

---

## 13. Ce qui reste modulaire et prêt à brancher plus tard

- **Mémoire contextuelle (ChromaDB)** : remplace `NoOpMemory` par l'implémentation complète du plan initial (phase 4) — aucune autre partie du code n'aura besoin de changer.
- **Décision IA (LangGraph)** : le point d'insertion est indiqué dans `on_change()` — appelle `llm_client.ask_local_llm(...)` avec le texte observé et le contexte mémoire.
- **Automatisation d'actions** : réutilise `actions/desktop_actions.py` du plan initial (whitelist anti-hallucination), appelée depuis l'orchestrateur de décision une fois celui-ci branché.

---

Teste d'abord `get_status` et `trigger_panic` isolément (même cycle GitHub Actions que d'habitude) avant de brancher la boucle d'observation complète — ça te confirme que la synchronisation par fichiers fonctionne avant d'ajouter la complexité de l'OCR et de la décision IA.
