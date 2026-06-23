import json
import re
from pathlib import Path
from typing import Any

import ollama

from config.settings import settings
from src.observability.tracing import observe


_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "metadata_extraction.md"


def extract_from_filename(path: Path) -> dict[str, Any]:
    """Extract annee_publication heuristically from filename."""
    name = path.stem
    year_match = re.search(r"(20\d{2}|19\d{2})", name)
    return {
        "annee_publication": int(year_match.group()) if year_match else None,
        "source": name,
    }


@observe(name="metadata_extraction_llm")
def extract_with_llm(text_sample: str) -> dict[str, Any]:
    """Ask the local LLM to extract structured metadata from a text excerpt."""
    prompt_template = _PROMPT_PATH.read_text(encoding="utf-8")
    prompt = prompt_template.replace("{{TEXT}}", text_sample[:2000])

    response = ollama.chat(
        model=settings.ollama_llm_model,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0},
    )
    raw = response["message"]["content"]

    # Extract JSON block from response
    json_match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    if json_match:
        raw = json_match.group(1)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}
