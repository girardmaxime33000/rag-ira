import re
from enum import Enum
from typing import Any

from src.retrieval import structured, vector

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


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
        year_match = _YEAR_RE.search(query)
        annee_reference = int(year_match.group()) if year_match else None
        # Sans année explicite, on ne peut pas cibler la table `facts` par mots-clés
        # (les noms de `metric` sont hétérogènes et ne recoupent pas le vocabulaire
        # naturel de la question) : `query_facts` applique quand même une LIMIT et
        # un DISTINCT pour éviter de renvoyer toute la table dans le prompt.
        results["facts"] = structured.query_facts(annee_reference=annee_reference)
        results["series_breaks"] = structured.get_series_breaks()
    else:
        results["facts"] = []
        results["series_breaks"] = []

    return results
