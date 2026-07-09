# Sentinel — Intégration du backend Python dans Tauri (guide pas à pas)

> Suite du plan initial. Tu as maintenant Tauri + Rust fonctionnels (démo "Welcome to Tauri" compilée avec succès). Ce document t'explique comment brancher ton backend Python dessus, concrètement.

---

## Clarification essentielle avant de commencer

Tu n'as **pas besoin de compiler ton backend Python en .exe à chaque modification**. Le mécanisme "sidecar" (PyInstaller + `externalBin`) ne sert qu'au moment de l'**empaquetage final** (créer l'installeur `.msi` que tu donneras à un client).

Pendant que tu codes, le workflow est beaucoup plus simple :
- Ton backend Python tourne comme un script normal (`python backend/main.py`) dans un terminal.
- Ton frontend React tourne avec `npm run tauri dev` dans un autre terminal, avec hot-reload comme avant.
- Les deux communiquent directement via WebSocket sur `localhost:8765` (le pont FastAPI qu'on a déjà codé dans le plan initial) — **sans passer par le mécanisme sidecar du tout**.

Le sidecar entre en jeu une seule fois, tout à la fin : il sert à ce que le programme Python démarre automatiquement quand ton client double-clique sur l'application installée, sans qu'il ait besoin d'installer Python lui-même.

Donc, réponse directe à ta question 4 : **oui, tu continues avec `npm run tauri dev`** (ou `npx tauri dev`, équivalent) pour voir tes modifications en temps réel. Ça ne change pas.

---

## 1. Structure du projet (réponse à ta question 1)

Vérifie où se trouve ton dossier `src-tauri` — c'est ton point de repère. Dans la structure standard générée par `create-tauri-app`, tu dois avoir :

```
sentinel-app/              <- racine de ton projet (le nom que tu as choisi à l'install)
├── src/                   <- ton frontend React (App.tsx, etc.)
├── src-tauri/
│   ├── src/
│   │   ├── main.rs        <- très court, appelle juste lib.rs
│   │   └── lib.rs         <- c'est ICI que la logique Rust s'écrit
│   ├── capabilities/
│   │   └── default.json   <- les permissions (dont celle du sidecar)
│   ├── binaries/          <- à créer toi-même, vide pour l'instant
│   └── tauri.conf.json
├── backend/                <- À CRÉER : tout ton code Python source va ici
│   ├── main.py
│   ├── vision/
│   ├── memory/
│   ├── ...
│   └── requirements.txt
└── package.json
```

Point important : **ton code Python source (`.py`) ne va jamais dans `src-tauri/binaries/`.** Ce dossier ne reçoit que le fichier `.exe` compilé, et seulement au moment du packaging final (Phase 11 du plan initial). Pendant le développement, `backend/` reste un dossier Python normal, à la racine du projet, à côté de `src-tauri/` et `src/`.

---

## 2. Configuration Tauri (réponse à ta question 2)

D'abord, installe le plugin shell — c'est lui qui gère les sidecars en Tauri v2 (ça a changé par rapport à la v1, qui l'intégrait au cœur du framework) :

```bash
# à la racine de ton projet (là où est package.json)
npm run tauri add shell
```

Cette commande fait automatiquement 3 choses : elle ajoute `tauri-plugin-shell` à `src-tauri/Cargo.toml`, elle enregistre le plugin dans `lib.rs`, et elle installe `@tauri-apps/plugin-shell` côté npm. Vérifie que c'est bien fait (regarde les fichiers), sinon fais-le à la main avec les commandes ci-dessous.

Ensuite, dans `src-tauri/tauri.conf.json`, ajoute `externalBin` dans la section `bundle` (en Tauri v2, il n'y a plus de clé `"tauri"` qui enveloppe tout — la structure est plus plate qu'en v1) :

```json
{
  "bundle": {
    "active": true,
    "targets": "all",
    "externalBin": ["binaries/sentinel-backend"]
  }
}
```

Le nom `binaries/sentinel-backend` est relatif à `tauri.conf.json`. Retiens-le, tu le réutilises identique à trois endroits (config, capabilities, code Rust).

---

## 3. Permissions — le fichier capabilities (nouveau par rapport au plan initial, propre à Tauri v2)

C'est une étape qui n'existait pas en v1 : Tauri v2 bloque tout par défaut pour la sécurité, et il faut déclarer explicitement le droit de lancer ton sidecar.

Dans `src-tauri/capabilities/default.json` :

```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "default",
  "description": "Capability for the main window",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "opener:default",
    {
      "identifier": "shell:allow-execute",
      "allow": [
        { "name": "binaries/sentinel-backend", "sidecar": true, "args": true }
      ]
    },
    "shell:allow-spawn",
    "shell:allow-kill"
  ]
}
```

Si tu obtiens une erreur du type "permission denied" ou "scope not allowed" au lancement du sidecar plus tard, c'est ce fichier qu'il faut regarder en premier.

---

## 4. Lien Frontend/Backend via Rust (réponse à ta question 3)

Voici le point clé à bien comprendre : **Rust ne sert qu'à démarrer et arrêter le processus Python**. Une fois que le serveur FastAPI tourne, ton React lui parle directement en WebSocket, sans repasser par Rust pour chaque message. C'est beaucoup plus simple que de faire transiter chaque appel par l'IPC Tauri.

Dans `src-tauri/src/lib.rs` :

```rust
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;
use std::sync::Mutex;

struct SidecarProcess(Mutex<Option<CommandChild>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(SidecarProcess(Mutex::new(None)))
        .setup(|app| {
            // Démarre le backend Python en même temps que la fenêtre Tauri
            let sidecar_command = app.shell().sidecar("sentinel-backend")?;
            let (mut _rx, child) = sidecar_command.spawn()?;

            let state: tauri::State<SidecarProcess> = app.state();
            *state.0.lock().unwrap() = Some(child);

            Ok(())
        })
        .on_window_event(|window, event| {
            // Tue le processus Python quand on ferme la fenêtre
            // (sinon il continue de tourner en arrière-plan indéfiniment)
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let state: tauri::State<SidecarProcess> = window.state();
                if let Some(child) = state.0.lock().unwrap().take() {
                    let _ = child.kill();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

Note : cette API a évolué plusieurs fois dans les versions récentes de `tauri-plugin-shell`. S'il y a une erreur de compilation sur `.shell()`, `.sidecar()` ou `.spawn()`, colle-moi le message d'erreur exact et je corrige la syntaxe — c'est le genre de détail qui varie d'une version mineure à l'autre.

Côté React, **tu n'as rien à changer** par rapport au code déjà prévu dans le plan initial — il se connecte directement au serveur :

```tsx
// src/App.tsx
useEffect(() => {
  const ws = new WebSocket("ws://127.0.0.1:8765/ws");
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "suggestion") setSuggestion(data.reason);
  };
  return () => ws.close();
}, []);
```

Le rôle de Rust s'arrête à "démarrer/arrêter le programme" — pas à faire transiter les données.

---

## 5. Workflow de développement au quotidien

Voici concrètement comment tu travailles maintenant, jour après jour :

**Terminal 1 — le backend Python (mode brut, pas de compilation) :**
```bash
cd backend
venv\Scripts\activate
python main.py
```

**Terminal 2 — le frontend + Tauri (comme pour ta démo) :**
```bash
npm run tauri dev
```

Tu modifies ton code React → rechargement automatique instantané (comme avant).
Tu modifies ton code Python → relance juste `python main.py` dans le terminal 1 (ou lance uvicorn avec `--reload` si tu veux l'auto-reload côté Python aussi).

**Tu n'as pas besoin du sidecar tant que tu es en phase de développement.** Il ne sert que pour la version que tu distribueras à un vrai cabinet.

---

## 6. Quand (et seulement quand) tu passes au packaging final

Cette étape, tu la fais une fois que le produit est fonctionnel et testé, pas maintenant :

```bash
# 1. Compiler le Python en exécutable autonome
pyinstaller --onefile --name sentinel-backend backend/main.py

# 2. Trouver ton target triple Windows
rustc -Vv
# cherche la ligne "host: x86_64-pc-windows-msvc"

# 3. Renommer et déplacer le binaire compilé
#    dist/sentinel-backend.exe  →  src-tauri/binaries/sentinel-backend-x86_64-pc-windows-msvc.exe

# 4. Builder l'installeur complet
npm run tauri build
```

C'est seulement à cette étape que le code Rust de la section 4 (spawn du sidecar) entre en jeu réellement — pendant `tauri dev`, tu n'as même pas besoin que le binaire existe dans `binaries/` pour que ton développement React avance.

---

## Récapitulatif de l'ordre des opérations

1. `npm run tauri add shell` à la racine du projet
2. Crée le dossier `backend/` à la racine (à côté de `src/` et `src-tauri/`)
3. Colle-y le code du plan initial (`main.py`, `vision/`, `memory/`, etc.)
4. Modifie `tauri.conf.json` (section 2 ci-dessus)
5. Modifie `capabilities/default.json` (section 3)
6. Modifie `lib.rs` (section 4) — compile avec `cargo build` dans `src-tauri/` pour vérifier que ça compile, même si le sidecar n'existe pas encore
7. Lance le workflow de dev (section 5) : Python dans un terminal, `npm run tauri dev` dans l'autre
8. Vérifie dans la fenêtre Tauri que le WebSocket se connecte (ouvre les DevTools avec F12 pour voir la console)
9. Continue de coder les modules du plan initial normalement
10. Packaging (section 6) seulement à la fin

Si une étape bloque (erreur de compilation Rust, erreur de connexion WebSocket, etc.), colle-moi le message d'erreur exact — je préfère corriger sur un vrai message plutôt que deviner.
