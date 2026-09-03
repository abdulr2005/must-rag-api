"""
Tests for FastAPI endpoints in rag_api.py:
- GET /
- POST /rag/search
- POST /chat
"""
import pytest
from fastapi.testclient import TestClient
from rag_api import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health_check(client):
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"


def test_rag_search_endpoint(client):
    payload = {"question": "What is AI.499?", "top_k": 3}
    res = client.post("/rag/search", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "results" in data
    assert len(data["results"]) > 0
    assert "text" in data["results"][0]


def test_chat_endpoint_valid_question(client):
    payload = {
        "question": "What is AI.499?",
        "history": [],
        "top_k": 3
    }
    res = client.post("/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "question" in data
    assert "answer" in data
    assert len(data["answer"]) > 0
    assert "context" in data
    assert "prompt_version" in data
    assert data["prompt_version"] == "1.0.0"


def test_chat_endpoint_validation_errors(client):
    # Question too short
    res = client.post("/chat", json={"question": "a"})
    assert res.status_code == 422

    # Missing question
    res = client.post("/chat", json={"top_k": 3})
    assert res.status_code == 422

    # top_k too large
    res = client.post("/chat", json={"question": "valid question", "top_k": 20})
    assert res.status_code == 422
