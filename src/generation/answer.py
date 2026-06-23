from pathlib import Path
from typing import Any

from src.generation.llm import generate
from src.retrieval.router import retrieve
from src.observability.tracing import observe

_GENERATION_PROMPT = (Path(__file__).parent.parent.parent / "prompts" / "generation.md").read_text


@observe(name="answer_query")
def answer(query: str) -> dict[str, Any]:
    context = retrieve(query)
    prompt_template = _GENERATION_PROMPT(encoding="utf-8")

    chunks_text = "\n\n".join(
        f"[chunk score={c.get('score', 'N/A'):.3f}] {c['text']}"
        for c in context.get("chunks", [])
    ) or "(aucun passage narratif pertinent trouvé)"

    facts_text = "\n".join(
        f"- {f['metric']} | {f['annee_reference']} | {f['perimetre']} | "
        f"{f['statistique']} | {f['value']} {f['unit']} | source: {f['source']}"
        for f in context.get("facts", [])
    ) or "(aucun fait chiffré trouvé)"

    breaks_text = "\n".join(
        f"⚠️ {b['concept']} : {b['avertissement']}"
        for b in context.get("series_breaks", [])
    ) or ""

    prompt = (
        prompt_template
        .replace("{{QUESTION}}", query)
        .replace("{{CHUNKS}}", chunks_text)
        .replace("{{FACTS}}", facts_text)
        .replace("{{SERIES_BREAKS}}", breaks_text)
    )

    response = generate(prompt)
    return {
        "query": query,
        "query_type": context["query_type"],
        "answer": response,
        "sources": {
            "chunks": context.get("chunks", []),
            "facts": context.get("facts", []),
            "series_breaks": context.get("series_breaks", []),
        },
    }
