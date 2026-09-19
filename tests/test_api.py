"""Tests du shim OpenAI-compatible — aucun accès réseau/Ollama/Postgres réel."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.openai_compat import app

client = TestClient(app)

_FAKE_RESULT = {
    "query": "Quel est le revenu médian ?",
    "query_type": "quantitative",
    "answer": "Le revenu médian est de 15 000 €.",
    "sources": {
        "chunks": [],
        "facts": [
            {
                "metric": "revenu_median",
                "annee_reference": 2022,
                "perimetre": "France entière, Urssaf",
                "statistique": "mediane",
                "value": 15000,
                "unit": "€ courants",
                "source": "Urssaf",
            }
        ],
        "series_breaks": [
            {
                "concept": "Effectifs artistes-auteurs",
                "avertissement": "Périmètres non comparables avant/après 2019.",
            }
        ],
    },
}


def test_list_models():
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"][0]["id"] == "rag-ira"


def test_chat_completions_non_streaming():
    question = "Quel est le revenu médian ?"
    with patch("src.api.openai_compat.answer", return_value=_FAKE_RESULT) as mocked:
        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "rag-ira",
                "messages": [{"role": "user", "content": question}],
            },
        )
    assert resp.status_code == 200
    mocked.assert_called_once_with(question)
    body = resp.json()
    content = body["choices"][0]["message"]["content"]
    assert "15 000 €" in content
    # Series-break warning and facts must surface for the user, not be silently dropped.
    assert "Périmètres non comparables" in content
    assert "Urssaf" in content


def test_chat_completions_requires_user_message():
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "rag-ira", "messages": [{"role": "system", "content": "hello"}]},
    )
    assert resp.status_code == 400


def test_chat_completions_rejects_bad_api_key():
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "rag-ira", "messages": [{"role": "user", "content": "salut"}]},
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert resp.status_code == 401
