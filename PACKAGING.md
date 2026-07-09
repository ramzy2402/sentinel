# Packaging Sentinel

1. Compiler le backend Python en exécutable autonome :
   `pyinstaller --onefile --name sentinel-backend backend/main.py`

2. Placer le binaire généré dans `src-tauri/binaries/` en le renommant avec le suffixe approprié pour Windows (ex: `sentinel-backend-x86_64-pc-windows-msvc.exe`).

3. Builder l'installeur final :
   `cd frontend`
   `npm run tauri build`
