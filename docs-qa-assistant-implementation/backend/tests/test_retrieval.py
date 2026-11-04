from pathlib import Path
from app.services.retrieval import load_documents, HybridRetriever, HashTestEncoder, chunk_text

DATA = Path(__file__).parents[1] / "app" / "data" / "docs.json"

def make_retriever(tmp_path):
    return HybridRetriever(load_documents(DATA), encoder=HashTestEncoder(),
                           persist_dir=tmp_path, collection_name="test_docs", rebuild=True)

def test_chunker_keeps_short_and_trailing_text():
    text = "x" * 1001
    chunks = chunk_text(text, chunk_size=400, overlap=50)
    rebuilt = chunks[0] + chunks[1][50:] + chunks[2][50:]
    assert rebuilt == text
    assert chunk_text("short text", 400) == ["short text"]

def test_chunk_ids_and_chroma_vector_index(tmp_path):
    r = make_retriever(tmp_path)
    assert r.chunks
    assert all(c["chunk_id"].startswith(c["doc_id"] + "-C") for c in r.chunks)
    assert r.collection.count() == len(r.chunks)

def test_supported_examples_retrieve_expected_documents(tmp_path):
    r = make_retriever(tmp_path)
    cases = [
        ("How do I reset my password?", "D-01"),
        ("How long do I have to use a password reset link before it expires?", "D-01"),
        ("What's the maximum number of rows I can export to CSV?", "D-03"),
        ("What are the API rate limits for the Growth plan?", "D-06"),
    ]
    for question, expected in cases:
        results = r.search(question, "Standard User")
        assert results and results[0]["doc_id"] == expected
        assert results[0]["hybrid_score"] > 0
        assert results[0]["hybrid_rank"] == 1

def test_unsupported_question_has_no_lexical_evidence(tmp_path):
    r = make_retriever(tmp_path)
    results = r.search("What is the salary?", "Standard User")
    assert not results or results[0]["lexical_overlap"] == 0

def test_role_filter_happens_before_both_retrieval_channels(tmp_path):
    docs = [{"doc_id":"SECRET-1","title":"Internal launch plan",
             "content":"Project Falcon launch codeword is amber.",
             "classification":"Internal",
             "allowed_roles":["Administrator","Support Agent"]}]
    r = HybridRetriever(docs, encoder=HashTestEncoder(), persist_dir=tmp_path,
                        collection_name="restricted", rebuild=True)
    assert r.search("Project Falcon launch codeword", "Standard User") == []
    assert r.search("Project Falcon launch codeword", "Support Agent")
