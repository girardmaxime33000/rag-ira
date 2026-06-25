import json
import re
from pathlib import Path
from typing import Any

import ollama
from docling_core.types.doc import TableItem

from config.settings import settings
from src.observability.tracing import observe

_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "table_extraction.md"

_VALID_STATISTIQUE = {"moyenne", "mediane", "total", "part"}
_VALID_NATURE_REVENU = {"artistique", "total", "na"}


def _table_to_text(table: TableItem) -> str:
    """Convert a Docling TableItem to a plain-text markdown-like representation."""
    try:
        df = table.export_to_dataframe()
        return df.to_string(index=False)
    except Exception:
        pass

    # Fallback: use markdown export
    try:
        return table.export_to_markdown()
    except Exception:
        return ""


def _validate_fact(fact: dict[str, Any]) -> dict[str, Any] | None:
    """Validate and coerce a raw LLM-extracted fact. Returns None if invalid."""
    try:
        value = float(fact["value"])
    except (KeyError, TypeError, ValueError):
        return None

    statistique = str(fact.get("statistique", "")).lower().strip()
    if statistique not in _VALID_STATISTIQUE:
        statistique = "total"

    nature_revenu = str(fact.get("nature_revenu", "na")).lower().strip()
    if nature_revenu not in _VALID_NATURE_REVENU:
        nature_revenu = "na"

    metric = str(fact.get("metric", "")).strip()
    if not metric:
        return None

    unit = str(fact.get("unit", "")).strip() or "non précisé"
    perimetre = str(fact.get("perimetre", "non précisé")).strip() or "non précisé"
    segment = str(fact.get("segment", "")).strip()
    fiabilite = str(fact.get("fiabilite", "normale")).strip()

    annee_reference = fact.get("annee_reference")
    if annee_reference is None:
        return None
    try:
        annee_reference = int(annee_reference)
    except (TypeError, ValueError):
        return None

    return {
        "metric": metric,
        "value": value,
        "unit": unit,
        "annee_reference": annee_reference,
        "perimetre": perimetre,
        "segment": segment,
        "statistique": statistique,
        "nature_revenu": nature_revenu,
        "fiabilite": fiabilite,
    }


@observe(name="table_extraction_llm")
def extract_facts_from_table(
    table: TableItem,
    *,
    source: str,
    annee_publication: int | None,
) -> list[dict[str, Any]]:
    """Ask the LLM to extract structured facts from a single Docling TableItem."""
    table_text = _table_to_text(table)
    if not table_text.strip():
        return []

    prompt_template = _PROMPT_PATH.read_text(encoding="utf-8")
    prompt = (
        prompt_template
        .replace("{{SOURCE}}", source)
        .replace("{{ANNEE_PUBLICATION}}", str(annee_publication or "inconnue"))
        .replace("{{TABLE}}", table_text[:3000])
    )

    response = ollama.chat(
        model=settings.ollama_llm_model,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0},
    )
    raw = response["message"]["content"]

    # Extract JSON array from response
    json_match = re.search(r"```json\s*(\[.*?\])\s*```", raw, re.DOTALL)
    if json_match:
        raw_json = json_match.group(1)
    else:
        array_match = re.search(r"\[.*\]", raw, re.DOTALL)
        raw_json = array_match.group() if array_match else "[]"

    try:
        raw_facts: list[dict] = json.loads(raw_json)
    except json.JSONDecodeError:
        return []

    validated = [_validate_fact(f) for f in raw_facts]
    return [f for f in validated if f is not None]


def parse_tables(
    tables: list[TableItem],
    *,
    source: str,
    annee_publication: int | None,
) -> list[dict[str, Any]]:
    """Process all tables from a document and return validated facts."""
    all_facts: list[dict[str, Any]] = []
    for i, table in enumerate(tables):
        try:
            facts = extract_facts_from_table(table, source=source, annee_publication=annee_publication)
            all_facts.extend(facts)
        except Exception as e:
            print(f"  [table {i+1}] erreur d'extraction : {e}")
    return all_facts
