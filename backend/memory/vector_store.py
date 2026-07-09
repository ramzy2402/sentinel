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
