import { defineConfig } from 'vite';

export default defineConfig({
  root: './',
  base: './',
  server: {
    port: 1420,
    strictPort: true,
  },
  build: {
    // Ceci aide Tauri à trouver les fichiers générés
    outDir: 'dist',
  }
});