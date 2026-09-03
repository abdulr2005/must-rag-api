"""
Reads questions from sample_questions.md and sends each one
to the RAG /rag/search endpoint.

Run:
    cd /Users/emmyel-sawy/Desktop/chatboy/must-rag-api-main
    source venv/bin/activate
    pytest tests/test_rag_questions.py -v
"""
import pathlib
import re
import requests
import pytest

RAG_URL = "http://localhost:8000/rag/search"

# ── load questions from the markdown file ──────────────────────────────────────
def load_questions():
    md = pathlib.Path(__file__).parent / "sample_questions.md"
    text = md.read_text(encoding="utf-8")
    # grab every line that starts with a number e.g.  "1. question text"
    questions = re.findall(r"^\d+\.\s+(.+)$", text, re.MULTILINE)
    # skip placeholder lines that contain a lone "X" or "Y" only
    return [q for q in questions if q.strip() not in ("X", "Y")]


# ── parametrized test ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("question", load_questions())
def test_rag_returns_results(question):
    """Each question must return at least one result with non‑empty content."""
    payload = {"question": question, "top_k": 3}
    resp = requests.post(RAG_URL, json=payload, timeout=30)
    assert resp.status_code == 200, f"HTTP {resp.status_code} for: {question}"
    data = resp.json()
    assert "results" in data, "Response missing 'results' key"
    assert len(data["results"]) > 0, f"No results returned for: {question}"
    for r in data["results"]:
        assert r.get("text"), f"Result has empty text. Keys found: {list(r.keys())}"
