from pathlib import Path
from app.services.retrieval import load_documents, Retriever, chunk_text
DATA = Path(__file__).parents[1] / "app" / "data" / "docs.json"

def make_retriever():
    return Retriever(load_documents(DATA))

def test_chunker_keeps_short_and_trailing_text():
    text = "x" * 1001
    chunks = chunk_text(text, chunk_size=400, overlap=50)
    rebuilt = chunks[0] + chunks[1][50:] + chunks[2][50:]
    assert rebuilt == text
    assert chunk_text("short text", 400) == ["short text"]

def test_supported_examples_retrieve_expected_docs():
    r = make_retriever()
    cases = [
        ("How do I reset my password?", "D-01"),
        ("How long do I have to use a password reset link before it expires?", "D-01"),
        ("What's the maximum number of rows I can export to CSV?", "D-03"),
        ("What are the API rate limits for the Growth plan?", "D-06"),
    ]
    for question, expected in cases:
        results = r.search(question, "Standard User")
        assert results and results[0]["doc_id"] == expected

def test_unsupported_salesforce_has_no_strong_match():
    r = make_retriever()
    results = r.search("Can I connect Solstice to Salesforce?", "Standard User")
    assert not results or results[0]["overlap"] <= 1

def test_role_filter_happens_in_retrieval():
    docs = [{"doc_id":"SECRET-1","title":"Internal plan","content":"Project Falcon internal launch codeword",
             "classification":"Internal","allowed_roles":["Administrator","Support Agent"]}]
    r = Retriever(docs)
    assert r.search("Project Falcon launch codeword","Standard User") == []
    assert r.search("Project Falcon launch codeword","Support Agent")
