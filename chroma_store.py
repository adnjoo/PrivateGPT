import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List

# Initialize Chroma persistent client and collection
_client = None
_collection = None
_embedder = None

def init_chroma(collection_name="chat_history", db_path="./chroma_db"):
    global _client, _collection, _embedder
    if _client is None:
        _client = chromadb.PersistentClient(path=db_path)
    _collection = _client.get_or_create_collection(collection_name)
    if _embedder is None:
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _collection

def save_message(text: str, user_id=None, role: str = "user", message_id=None):
    """
    Save a message to the vector memory with its embedding and role metadata.
    """
    if _collection is None or _embedder is None:
        raise RuntimeError("Chroma collection and embedder not initialized. Call init_chroma() first.")
    embedding = _embedder.encode(text).tolist()
    meta = {"role": role}
    if user_id is not None:
        meta["user_id"] = user_id
    doc_id = f"{role}_{user_id}_{message_id}" if user_id and message_id else f"{role}_{hash(text)}"
    _collection.add(
        documents=[text],
        embeddings=[embedding],
        metadatas=[meta],
        ids=[doc_id]
    )

def get_similar_messages(query: str, top_k: int = 3) -> List[str]:
    """
    Retrieve top_k most similar messages from memory to the query.
    """
    if _collection is None or _embedder is None:
        raise RuntimeError("Chroma collection and embedder not initialized. Call init_chroma() first.")
    embedding = _embedder.encode(query).tolist()
    results = _collection.query(
        query_embeddings=[embedding],
        n_results=top_k,
        include=["documents", "metadatas"]
    )
    print(f"[VectorDB] Query: '{query}' → Matches: {results['documents'][0]}")
    return results["documents"][0] if results["documents"] else []

def get_collection():
    if _collection is None:
        raise RuntimeError("Chroma collection not initialized. Call init_chroma() first.")
    return _collection 