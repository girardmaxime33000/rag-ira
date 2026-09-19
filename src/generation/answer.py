from pathlib import Path
from typing import Any

from src.generation.llm import generate
from src.retrieval.router import retrieve
from src.observability.tracing import observe

_GENERATION_PROMPT = (Path(__file__).parent.parent.parent / "prompts" / "generation.md").read_text


def _strip_echoed_reference_lines(response: str, *reference_blocks: str) -> str:
    """Retire du texte généré les lignes qui reproduisent tel quel le matériel de
    référence injecté dans le prompt (facts/ruptures) : un petit modèle local
    (qwen3:4b) a tendance à recopier ces blocs bruts en plus de sa propre
    reformulation, au lieu de s'en servir uniquement comme contexte."""
    reference_lines = {
        stripped
        for block in reference_blocks
        for line in block.splitlines()
        if (stripped := line.strip().lstrip("-*").strip())
    }
    kept = [
        line
        for line in response.splitlines()
        if line.strip().lstrip("-*").strip() not in reference_lines
    ]
    return "\n".join(kept).strip()


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
    response = _strip_echoed_reference_lines(response, facts_text, breaks_text)
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
