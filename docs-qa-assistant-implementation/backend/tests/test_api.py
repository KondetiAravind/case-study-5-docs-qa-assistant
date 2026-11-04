import os
os.environ["APP_ENV"] = "test"

from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["documents_loaded"] == 6
    assert body["vector_database"] == "ChromaDB"

def test_auth_required():
    response = client.post("/api/ask", json={"question":"How do I reset my password?"})
    assert response.status_code == 401

def test_supported_question_returns_chunk_and_scores():
    response = client.post("/api/ask", headers={"X-Demo-User":"standard"},
        json={"question":"How long does a reset link last?"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["sources"][0]["doc_id"] == "D-01"
    assert body["sources"][0]["chunk_id"].startswith("D-01-C")
    assert body["sources"][0]["hybrid_score"] > 0
    assert "lexical_score" in body["sources"][0]
    assert "semantic_similarity" in body["sources"][0]
    assert "chunk_index" in body["sources"][0]

def test_salesforce_abstains():
    response = client.post("/api/ask", headers={"X-Demo-User":"standard"},
        json={"question":"Can I connect Solstice to Salesforce?"})
    assert response.status_code == 200
    assert response.json()["status"] == "not_found"

def test_conversation_id_is_returned_and_reused():
    cid = "conversation_123"
    first = client.post("/api/ask", headers={"X-Demo-User":"standard"},
        json={"question":"What is the API rate limit for the Growth plan?", "conversation_id":cid})
    assert first.status_code == 200
    second = client.post("/api/ask", headers={"X-Demo-User":"standard"},
        json={"question":"What about Enterprise?", "conversation_id":cid})
    assert second.status_code == 200
    assert second.json()["conversation_id"] == cid
