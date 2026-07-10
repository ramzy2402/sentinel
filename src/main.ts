import { invoke } from "@tauri-apps/api/core";
console.log("[Sentinel] main.ts chargé, initialisation...");
if (!("__TAURI_INTERNALS__" in window)) {
  console.error("[Sentinel] Pas dans une fenêtre Tauri — invoke() ne fonctionnera pas ici.");
}
const panicBtn = document.getElementById("panic-btn") as HTMLButtonElement | null;
const statusBadge = document.getElementById("status-badge") as HTMLElement | null;
const statusLabel = document.getElementById("status-label") as HTMLElement | null;
const logList = document.getElementById("log-list") as HTMLElement | null;
if (!panicBtn) console.error("[Sentinel] Élément #panic-btn introuvable dans le DOM.");
function addLogLine(text: string) {
  console.log(`[Sentinel] ${text}`);
  if (logList) {
    const line = document.createElement("div");
    line.className = "log-line";
    line.textContent = `${new Date().toLocaleTimeString()} — ${text}`;
    logList.prepend(line);
  }
}
async function triggerPanic() {
  console.log("[Sentinel] Clic sur panic-btn -> invoke('trigger_panic')");
  try {
    const rawResponse = await invoke<string>("trigger_panic");
    console.log("[Sentinel] Réponse brute du backend Python :", rawResponse);
    addLogLine(`Bouton panique confirmé : ${rawResponse}`);
    if (statusBadge) statusBadge.dataset.phase = "pause";
    if (statusLabel) statusLabel.textContent = "En pause";
  } catch (error) {
    console.error("[Sentinel] Erreur trigger_panic :", error);
    addLogLine(`Erreur : ${error}`);
  }
}
panicBtn?.addEventListener("click", triggerPanic);
console.log("[Sentinel] Initialisation terminée.");