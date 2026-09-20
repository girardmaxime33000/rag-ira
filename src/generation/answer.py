import difflib
import re
from pathlib import Path
from typing import Any

from src.generation.llm import generate
from src.observability.tracing import observe
from src.retrieval.router import retrieve

_GENERATION_PROMPT = (Path(__file__).parent.parent.parent / "prompts" / "generation.md").read_text

_ECHO_SIMILARITY_THRESHOLD = 0.85


def _normalize_for_echo_match(line: str) -> str:
    """Réduit une ligne à son contenu textuel comparable : puce, casse,
    ponctuation et espaces multiples ignorés. Le LLM (temperature=0.1)
    reproduit rarement les blocs de référence caractère pour caractère —
    guillemets typographiques, espace insécable ou point final en plus/moins
    suffisent à faire échouer une comparaison exacte."""
    line = line.strip().lstrip("-*").strip()
    line = re.sub(r"[^\w]+", " ", line.lower())
    return re.sub(r"\s+", " ", line).strip()


def _strip_echoed_reference_lines(response: str, *reference_blocks: str) -> str:
    """Retire du texte généré les lignes qui reproduisent le matériel de
    référence injecté dans le prompt (facts/ruptures) : un petit modèle local
    (qwen3:4b) a tendance à recopier ces blocs en plus de sa propre
    reformulation, au lieu de s'en servir uniquement comme contexte. La
    comparaison est approximative (ratio de similarité), pas une égalité
    stricte, pour rester robuste aux micro-reformulations du modèle."""
    reference_lines = [
        normalized
        for block in reference_blocks
        for line in block.splitlines()
        if (normalized := _normalize_for_echo_match(line))
    ]

    def _is_echo(line: str) -> bool:
        normalized = _normalize_for_echo_match(line)
        if not normalized:
            return False
        return any(
            difflib.SequenceMatcher(None, normalized, ref).ratio()
            >= _ECHO_SIMILARITY_THRESHOLD
            for ref in reference_lines
        )

    kept = [line for line in response.splitlines() if not _is_echo(line)]
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

    coverage = context.get("coverage")
    if coverage and coverage.get("annee_min") is not None:
        coverage_text = (
            f"Les `facts` de la base couvrent les années {coverage['annee_min']} "
            f"à {coverage['annee_max']} inclus "
            f"({coverage['nombre_facts']} faits au total). "
            "Cette plage porte sur la disponibilité des données, pas sur leur "
            "comparabilité : voir la section Ruptures de série ci-dessous pour "
            "les périodes non comparables entre elles."
        )
    else:
        coverage_text = "(couverture temporelle non disponible)"

    prompt = (
        prompt_template
        .replace("{{QUESTION}}", query)
        .replace("{{CHUNKS}}", chunks_text)
        .replace("{{FACTS}}", facts_text)
        .replace("{{COVERAGE}}", coverage_text)
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
            "coverage": coverage,
        },
    }
