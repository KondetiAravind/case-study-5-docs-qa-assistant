from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["documents_loaded"] == 6

def test_auth_required():
    response = client.post("/api/ask",json={"question":"How do I reset my password?"})
    assert response.status_code == 401

def test_supported_question_returns_source():
    response = client.post("/api/ask",headers={"X-Demo-User":"standard"},
                           json={"question":"How long does a reset link last?"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["sources"][0]["doc_id"] == "D-01"

def test_salesforce_abstains():
    response = client.post("/api/ask",headers={"X-Demo-User":"standard"},
                           json={"question":"Can I connect Solstice to Salesforce?"})
    assert response.status_code == 200
    assert response.json()["status"] == "not_found"
    assert response.json()["sources"] == []
