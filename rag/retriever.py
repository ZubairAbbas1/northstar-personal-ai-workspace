import logging
from typing import Any

from rag.config import CHROMA_DIR, COLLECTION_NAME
from rag.ingest import get_embedding_function

logger = logging.getLogger(__name__)


def query_vault(query: str, top_k: int = 4) -> list[dict[str, Any]]:
    """Performs semantic similarity search over stored personal documents."""
    if not query.strip():
        return []

    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        collection = client.get_or_create_collection(name=COLLECTION_NAME)

        count = collection.count()
        if count == 0:
            return []

        embeddings_fn = get_embedding_function()
        query_vector = embeddings_fn.embed_query(query)

        results = collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, count),
        )

        matches = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if "metadatas" in results and results["metadatas"] else [{}] * len(docs)
            distances = results["distances"][0] if "distances" in results and results["distances"] else [0.0] * len(docs)

            for doc, meta, dist in zip(docs, metas, distances):
                matches.append({
                    "content": doc,
                    "source": meta.get("source", "Document"),
                    "path": meta.get("path", ""),
                    "score": round(1.0 - (dist if dist is not None else 0.5), 3),
                })

        return matches
    except Exception as e:
        logger.warning("RAG retrieval failed: %s", e)
        return []
