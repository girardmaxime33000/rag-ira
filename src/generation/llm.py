from typing import Any

import ollama

from config.settings import settings
from src.observability.tracing import observe


@observe(name="llm_generate")
def generate(prompt: str, system: str | None = None) -> str:
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = ollama.chat(
        model=settings.ollama_llm_model,
        messages=messages,
        options={"temperature": 0.1},
    )
    return str(response["message"]["content"])
