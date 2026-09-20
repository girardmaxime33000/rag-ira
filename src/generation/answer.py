import difflib
import re
from pathlib import Path
from typing import Any

from src.generation.llm import generate
from src.observability.tracing import observe
from src.retrieval.router import retrieve

_GENERATION_PROMPT = (Path(__file__).parent.parent.parent / "prompts" / "generation.md").read_text

_ECHO_SIMILARITY_THRESHOLD = 0.85
# Sous ce seuil de longueur, une comparaison floue par fenêtre glissante est
# sujette aux faux positifs (deux courtes chaînes normalisées se ressemblent
# facilement par hasard) : on exige une correspondance de ligne normalisée
# quasi exacte à la place.
_MIN_REFERENCE_LEN_FOR_FUZZY_SPAN = 120


def _normalize_for_echo_match(text: str) -> str:
    """Réduit un texte à son contenu comparable : puce, casse, ponctuation et
    espaces multiples ignorés. Le LLM (temperature=0.1) reproduit rarement les
    blocs de référence caractère pour caractère — guillemet typographique,
    espace insécable ou point final en plus/moins suffisent à faire échouer
    une comparaison exacte."""
    text = text.strip().lstrip("-*").strip()
    text = re.sub(r"[^\w]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _remove_best_matching_span(text: str, reference: str, threshold: float) -> str:
    """Cherche dans `text` la sous-chaîne qui ressemble le plus à `reference`
    (fenêtre glissante, tailles ~0.85x/1x/1.15x la longueur de la référence)
    et la retire si la similarité dépasse le seuil. Contrairement à une
    comparaison ligne par ligne, ceci fonctionne même quand le modèle colle
    plusieurs avertissements sur un même paragraphe sans saut de ligne."""
    ref_norm = _normalize_for_echo_match(reference)
    if not ref_norm or not text:
        return text

    ref_len = len(reference)
    step = max(10, ref_len // 10)
    best_ratio = 0.0
    best_span: tuple[int, int] | None = None

    for factor in (0.85, 1.0, 1.15):
        window_len = int(ref_len * factor)
        if window_len <= 0:
            continue
        last_start = max(len(text) - window_len, 0)
        for start in range(0, last_start + step, step):
            start = min(start, last_start)
            window = text[start : start + window_len]
            ratio = difflib.SequenceMatcher(
                None, _normalize_for_echo_match(window), ref_norm
            ).ratio()
            if ratio > best_ratio:
                best_ratio, best_span = ratio, (start, start + window_len)
            if start == last_start:
                break

    if best_span and best_ratio >= threshold:
        start, end = best_span
        return text[:start] + text[end:]
    return text


def _strip_echoed_reference_lines(response: str, *reference_blocks: str) -> str:
    """Retire du texte généré les passages qui reproduisent le matériel de
    référence injecté dans le prompt (facts/ruptures/couverture) : un petit
    modèle local a tendance à recopier ces blocs en plus de sa propre
    reformulation, au lieu de s'en servir uniquement comme contexte.

    Deux stratégies selon la longueur de la référence : les lignes courtes
    (bullets de facts, une par ligne côté modèle en pratique) sont comparées
    par égalité de ligne normalisée ; les phrases longues (ruptures,
    couverture) passent par une recherche de fenêtre glissante, car le
    modèle les colle parfois à la suite sur un même paragraphe sans saut de
    ligne, ce qu'une comparaison ligne à ligne ne détecte pas."""
    references = [
        line.strip()
        for block in reference_blocks
        for line in block.splitlines()
        if line.strip()
    ]

    short_refs = {
        _normalize_for_echo_match(r)
        for r in references
        if len(r) < _MIN_REFERENCE_LEN_FOR_FUZZY_SPAN
    }
    if short_refs:
        response = "\n".join(
            line
            for line in response.splitlines()
            if _normalize_for_echo_match(line) not in short_refs
        )

    for reference in references:
        if len(reference) >= _MIN_REFERENCE_LEN_FOR_FUZZY_SPAN:
            response = _remove_best_matching_span(
                response, reference, _ECHO_SIMILARITY_THRESHOLD
            )

    return response.strip()


def format_sources(sources: dict[str, Any]) -> str:
    """Rendu déterministe des sources (couverture/ruptures/facts/chunks), à
    ajouter en pied de réponse — CLI et shim OpenAI compatible partagent
    cette fonction pour ne montrer qu'une seule version, fiable, de ces
    chiffres : voir CLAUDE.md §8 et `_strip_echoed_reference_lines` ci-dessus,
    qui retire les tentatives du LLM de les retranscrire lui-même."""
    parts: list[str] = []

    coverage = sources.get("coverage")
    if coverage and coverage.get("annee_min") is not None:
        parts.append(
            "**Couverture temporelle des données :** "
            f"{coverage['annee_min']} à {coverage['annee_max']} "
            f"({coverage['nombre_facts']} faits au total)."
        )

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
        chunk_lines = []
        for c in chunks:
            src = c.get("doc_source") or c.get("metadata", {}).get("source")
            chunk_lines.append(f"- {src or 'source inconnue'}")
        parts.append("**Passages narratifs cités :**\n" + "\n".join(chunk_lines))

    if not parts:
        return ""
    return "\n\n---\n" + "\n\n".join(parts)


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
    response = _strip_echoed_reference_lines(
        response, facts_text, breaks_text, coverage_text
    )
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
