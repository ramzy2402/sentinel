import { invoke } from "@tauri-apps/api/core";

// --- Gestion du formulaire par défaut de Tauri ---
let greetInputEl: HTMLInputElement | null;
let greetMsgEl: HTMLElement | null;

async function greet() {
  if (greetMsgEl && greetInputEl) {
    greetMsgEl.textContent = await invoke("greet", {
      name: greetInputEl.value,
    });
  }
}

window.addEventListener("DOMContentLoaded", () => {
  greetInputEl = document.querySelector("#greet-input");
  greetMsgEl = document.querySelector("#greet-msg");
  document.querySelector("#greet-form")?.addEventListener("submit", (e) => {
    e.preventDefault();
    greet();
  });

  // --- Ton nouveau bouton de test Python ---
  document.getElementById("test-btn")?.addEventListener("click", async () => {
    try {
      const result = await invoke<string>("call_python", { message: "Hello Python" });
      const respEl = document.getElementById("response");
      if (respEl) respEl.textContent = result;
    } catch (error) {
      console.error("Erreur Python:", error);
    }
  });
});