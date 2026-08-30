import hashlib
import logging
from pathlib import Path
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.config import CHROMA_DIR, COLLECTION_NAME, OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL

logger = logging.getLogger(__name__)


def get_embedding_function():
    """Returns Ollama embeddings or a lightweight fallback embedding function."""
    try:
        from langchain_community.embeddings import OllamaEmbeddings
        embeddings = OllamaEmbeddings(
            base_url=OLLAMA_BASE_URL,
            model=OLLAMA_EMBED_MODEL,
        )
        # Test probe
        embeddings.embed_query("test")
        return embeddings
    except Exception as e:
        logger.warning("Ollama embeddings unavailable (%s), using local fallback embeddings.", e)

        class FallbackEmbeddings:
            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                return [self._embed(t) for t in texts]

            def embed_query(self, text: str) -> list[float]:
                return self._embed(text)

            def _embed(self, text: str) -> list[float]:
                # Deterministic 128-dim normalized embedding based on sha256 + char ngrams
                vec = [0.0] * 128
                for i, char in enumerate(text.lower()[:500]):
                    vec[ord(char) % 128] += 1.0
                norm = sum(x**2 for x in vec) ** 0.5 or 1.0
                return [x / norm for x in vec]

        return FallbackEmbeddings()


def load_file_content(file_path: Path) -> str:
    """Reads content from PDF, Markdown, Text, or DOCX files."""
    suffix = file_path.suffix.lower()

    if suffix in (".txt", ".md", ".markdown"):
        return file_path.read_text(encoding="utf-8", errors="ignore")

    elif suffix == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(pages)
        except Exception as e:
            logger.warning("Failed to parse PDF %s: %s", file_path, e)
            return ""

    elif suffix in (".docx", ".doc"):
        try:
            import docx
            doc = docx.Document(str(file_path))
            return "\n".join([p.text for p in doc.paragraphs])
        except Exception as e:
            logger.warning("Failed to parse DOCX %s: %s", file_path, e)
            return ""

    return ""


def ingest_document(file_path: Path) -> int:
    """Chunks and indexes a single document into ChromaDB."""
    content = load_file_content(file_path)
    if not content.strip():
        logger.warning("No extractable content found in %s", file_path)
        return 0

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
    )
    chunks = splitter.split_text(content)
    if not chunks:
        return 0

    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        collection = client.get_or_create_collection(name=COLLECTION_NAME)

        embeddings_fn = get_embedding_function()
        vectors = embeddings_fn.embed_documents(chunks)

        ids = [f"{file_path.name}_{i}_{hashlib.md5(c.encode()).hexdigest()[:8]}" for i, c in enumerate(chunks)]
        metadatas = [{"source": file_path.name, "path": str(file_path), "chunk_index": i} for i in range(len(chunks))]

        collection.upsert(
            ids=ids,
            embeddings=vectors,
            documents=chunks,
            metadatas=metadatas,
        )
        logger.info("Successfully ingested %d chunks for %s", len(chunks), file_path.name)
        return len(chunks)
    except Exception as e:
        logger.exception("Error ingesting document %s into Chroma: %s", file_path, e)
        return 0


def ingest_directory(directory_path: Path) -> dict[str, int]:
    """Ingests all supported files in a directory."""
    results = {}
    for p in directory_path.glob("**/*"):
        if p.is_file() and p.suffix.lower() in (".pdf", ".txt", ".md", ".docx"):
            count = ingest_document(p)
            results[p.name] = count
    return results
