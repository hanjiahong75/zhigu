"""Memory service: ChromaDB vector store for analysis memories."""
import os
import uuid
import logging
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from ..config import CHROMA_DB_PATH, CHROMA_COLLECTION, EMBEDDING_MODEL

logger = logging.getLogger(__name__)

# Lazy init globals
_client: Optional[chromadb.PersistentClient] = None
_collection: Optional[object] = None
_model: Optional[SentenceTransformer] = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        os.makedirs(CHROMA_DB_PATH, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=CHROMA_DB_PATH,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def _get_collection() -> object:
    global _collection
    if _collection is None:
        client = _get_client()
        _collection = client.get_or_create_collection(
            name=CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _embed(text: str) -> list[float]:
    model = _get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def store_memory(
    stock_code: str,
    stock_name: str,
    user_message: str,
    analysis_content: str,
    memory_id: Optional[str] = None,
) -> str:
    """Store an analysis as a vector memory in ChromaDB.

    Returns the memory ID.
    """
    collection = _get_collection()
    mid = memory_id or str(uuid.uuid4())

    # Combine user message + key analysis points for embedding
    doc_text = f"[{stock_name} {stock_code}] 用户提问: {user_message}\n分析要点: {analysis_content[:800]}"
    embedding = _embed(doc_text)

    collection.add(
        ids=[mid],
        embeddings=[embedding],
        metadatas=[{
            "stock_code": stock_code,
            "stock_name": stock_name,
            "user_message": user_message[:200],
            "created_at": "",  # filled by caller via upsert if needed
        }],
        documents=[doc_text],
    )
    return mid


def retrieve_memories(
    stock_code: str,
    query: str,
    n_results: int = 5,
) -> list[dict]:
    """Semantic search for relevant past analysis memories.

    Searches within the same stock_code scope, then falls back to cross-stock.
    """
    collection = _get_collection()
    query_embedding = _embed(query)

    # Try scoped search first
    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results * 2,
            where={"stock_code": stock_code},
            include=["metadatas", "documents", "distances"],
        )
    except Exception:
        results = {"ids": [[]], "metadatas": [[]], "documents": [[]], "distances": [[]]}

    memories = []
    if results["ids"] and results["ids"][0]:
        for i, mid in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"][0] else {}
            doc = results["documents"][0][i] if results["documents"][0] else ""
            dist = results["distances"][0][i] if results["distances"][0] else 1.0
            memories.append({
                "id": mid,
                "stock_code": meta.get("stock_code", ""),
                "stock_name": meta.get("stock_name", ""),
                "user_message": meta.get("user_message", ""),
                "document": doc,
                "relevance": round(1.0 - min(dist, 1.0), 3),
            })

    # If not enough results, try cross-stock search
    if len(memories) < n_results:
        try:
            cross_results = collection.query(
                query_embeddings=[query_embedding],
                n_results=max(1, n_results - len(memories)),
                include=["metadatas", "documents", "distances"],
            )
            if cross_results["ids"] and cross_results["ids"][0]:
                for i, mid in enumerate(cross_results["ids"][0]):
                    meta = cross_results["metadatas"][0][i] if cross_results["metadatas"][0] else {}
                    doc = cross_results["documents"][0][i] if cross_results["documents"][0] else ""
                    dist = cross_results["distances"][0][i] if cross_results["distances"][0] else 1.0
                    if meta.get("stock_code") != stock_code:
                        memories.append({
                            "id": mid,
                            "stock_code": meta.get("stock_code", ""),
                            "stock_name": meta.get("stock_name", ""),
                            "user_message": meta.get("user_message", ""),
                            "document": doc,
                            "relevance": round(1.0 - min(dist, 1.0), 3),
                        })
        except Exception:
            pass

    return memories[:n_results]


def build_memory_context(
    stock_code: str,
    user_message: str,
    n_results: int = 5,
) -> str:
    """Build a context string from relevant past memories for prompt injection."""
    query = f"分析股票 {stock_code} {user_message}"
    memories = retrieve_memories(stock_code, query, n_results)

    if not memories:
        return ""

    lines = [f"## 历史相关分析（语义检索，共{len(memories)}条）"]
    for i, m in enumerate(memories, 1):
        tag = " [跨股]" if m["stock_code"] != stock_code else ""
        lines.append(
            f"{i}. [{m['stock_name']}({m['stock_code']}){tag}] "
            f"相关度: {m['relevance']}"
        )
        lines.append(f"   内容: {m['document'][:250]}...")
    return "\n".join(lines)


def delete_stock_memories(stock_code: str) -> int:
    """Delete all memories for a stock. Returns count of deleted items."""
    collection = _get_collection()
    try:
        results = collection.get(where={"stock_code": stock_code})
        if results["ids"]:
            collection.delete(ids=results["ids"])
            return len(results["ids"])
    except Exception:
        pass
    return 0


def get_memory_count(stock_code: Optional[str] = None) -> int:
    """Count memories, optionally filtered by stock_code."""
    collection = _get_collection()
    try:
        if stock_code:
            results = collection.get(where={"stock_code": stock_code})
        else:
            results = collection.get()
        return len(results["ids"]) if results["ids"] else 0
    except Exception:
        return 0
