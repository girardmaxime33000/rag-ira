"""Serveur HTTP local exposant un endpoint compatible OpenAI (/v1/chat/completions)
pour brancher une UI externe (Open WebUI) sur le pipeline RAG.

Ceci ne contacte jamais OpenAI : c'est un simple shim qui reproduit le format
de câblage `chat/completions` par-dessus `src.generation.answer.answer`, qui
reste 100% local (Ollama + Postgres). Voir CLAUDE.md §1 et §8.
"""
import time
import uuid
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from config.settings import settings
from src.generation.answer import answer

app = FastAPI(title="rag-ira (OpenAI-compatible shim)")

MODEL_ID = "rag-ira"


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = MODEL_ID
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None


def _check_auth(request: Request) -> None:
    """Vérifie la clé Bearer si le client en fournit une (cf. Open WebUI)."""
    auth = request.headers.get("authorization")
    if auth is None:
        return
    token = auth.removeprefix("Bearer ")
    if not auth.startswith("Bearer ") or token != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _last_user_message(messages: list[ChatMessage]) -> str:
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    raise HTTPException(status_code=400, detail="Aucun message 'user' dans la requête")


def _format_sources(sources: dict[str, Any]) -> str:
    parts: list[str] = []

    breaks = sources.get("series_breaks") or []
    if breaks:
        break_lines = [f"⚠️ {b['concept']} : {b['avertissement']}" for b in breaks]
        parts.append("\n".join(break_lines))

    facts = sources.get("facts") or []
    if facts:
        fact_lines = [
            f"- {f['metric']} | {f['annee_reference']} | {f['perimetre']} | "
            f"{f['statistique']} | {f['value']} {f['unit']} | source: {f['source']}"
            for f in facts
        ]
        parts.append("**Faits chiffrés (`facts`) :**\n" + "\n".join(fact_lines))

    chunks = sources.get("chunks") or []
    if chunks:
        chunk_lines = [
            f"- {c.get('metadata', {}).get('source', 'source inconnue')}"
            for c in chunks
        ]
        parts.append("**Passages narratifs cités :**\n" + "\n".join(chunk_lines))

    if not parts:
        return ""
    return "\n\n---\n" + "\n\n".join(parts)


def _chat_completion_payload(query: str) -> dict[str, Any]:
    result = answer(query)
    content = result["answer"] + _format_sources(result.get("sources", {}))
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL_ID,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@app.get("/v1/models")
def list_models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_ID,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "rag-ira",
            }
        ],
    }


@app.post("/v1/chat/completions")
def chat_completions(body: ChatCompletionRequest, request: Request) -> Any:
    _check_auth(request)
    query = _last_user_message(body.messages)
    payload = _chat_completion_payload(query)

    if not body.stream:
        return payload

    from fastapi.responses import StreamingResponse

    def _sse() -> Any:
        content = payload["choices"][0]["message"]["content"]
        chunk_base = {
            "id": payload["id"],
            "object": "chat.completion.chunk",
            "created": payload["created"],
            "model": MODEL_ID,
        }
        first_choice = {
            "index": 0,
            "delta": {"role": "assistant"},
            "finish_reason": None,
        }
        yield f"data: {_dump({**chunk_base, 'choices': [first_choice]})}\n\n"
        step = 40
        for i in range(0, len(content), step):
            piece_choice = {
                "index": 0,
                "delta": {"content": content[i : i + step]},
                "finish_reason": None,
            }
            yield f"data: {_dump({**chunk_base, 'choices': [piece_choice]})}\n\n"
        last_choice = {"index": 0, "delta": {}, "finish_reason": "stop"}
        yield f"data: {_dump({**chunk_base, 'choices': [last_choice]})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_sse(), media_type="text/event-stream")


def _dump(obj: dict[str, Any]) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)
