from backend.memory.vector_store import store_event, query_similar
from backend.security.anonymizer import anonymize

def test():
    print("--- Test Anonymisation ---")
    raw = "Mon nom est Jean Dupont et mon IBAN est FR7612345678901234567890123"
    anon = anonymize(raw)
    print(f"Original : {raw}")
    print(f"Anon     : {anon}")

    print("\n--- Test Mémoire ---")
    store_event("Projet client A en cours", "Excel")
    store_event("Analyse patrimoine client B", "PDF")
    
    results = query_similar("client A")
    print(f"Résultats similaires : {results}")

if __name__ == "__main__":
    test()
