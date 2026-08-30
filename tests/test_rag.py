from pathlib import Path
from rag.ingest import get_embedding_function, ingest_document
from rag.retriever import query_vault


def test_embedding_function():
    embed_fn = get_embedding_function()
    assert embed_fn is not None
    vec = embed_fn.embed_query("Hello world testing embedding")
    assert isinstance(vec, list)
    assert len(vec) > 0


def test_document_ingest_and_query(tmp_path: Path):
    sample_file = tmp_path / "project_brief.txt"
    sample_file.write_text("Project Zenith pricing plan: The enterprise tier is priced at $500/month with unlimited seats.", encoding="utf-8")

    chunks_count = ingest_document(sample_file)
    assert chunks_count >= 1

    matches = query_vault("What is the enterprise tier price for Project Zenith?", top_k=2)
    assert len(matches) > 0
    assert "Zenith" in matches[0]["content"]
