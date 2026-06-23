from enum import Enum
from typing import Any

from src.retrieval import vector, structured


class QueryType(str, Enum):
    QUALITATIVE = "qualitative"
    QUANTITATIVE = "quantitative"
    HYBRID = "hybrid"


_NUMERIC_KEYWORDS = {
    "combien", "nombre", "effectif", "revenu", "salaire", "chiffre", "montant",
    "évolution", "pourcentage", "part", "moyenne", "médiane", "total", "€", "%",
    "euros", "dollar", "usd", "valeur", "statistique", "données",
}


def classify(query: str) -> QueryType:
    lower = query.lower()
    hits = sum(1 for kw in _NUMERIC_KEYWORDS if kw in lower)
    if hits >= 2:
        return QueryType.QUANTITATIVE
    if hits == 1:
        return QueryType.HYBRID
    return QueryType.QUALITATIVE


def retrieve(query: str, top_k: int = 5) -> dict[str, Any]:
    qtype = classify(query)
    results: dict[str, Any] = {"query_type": qtype}

    if qtype in (QueryType.QUALITATIVE, QueryType.HYBRID):
        results["chunks"] = vector.search(query, top_k=top_k)
    else:
        results["chunks"] = []

    if qtype in (QueryType.QUANTITATIVE, QueryType.HYBRID):
        results["facts"] = structured.query_facts()
        results["series_breaks"] = structured.get_series_breaks()
    else:
        results["facts"] = []
        results["series_breaks"] = []

    return results
