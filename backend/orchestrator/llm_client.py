import ollama

DEFAULT_MODEL = "qwen3:8b"

def ask_local_llm(prompt: str, model: str = DEFAULT_MODEL) -> str:
    try:
        response = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}])
        return response["message"]["content"]
    except Exception as e:
        return f"[Erreur LLM local] {e}"