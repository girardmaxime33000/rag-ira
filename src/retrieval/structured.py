from typing import Any

import psycopg

from config.settings import settings


def query_facts(
    *,
    metric: str | None = None,
    annee_reference: int | None = None,
    perimetre: str | None = None,
    statistique: str | None = None,
    nature_revenu: str | None = None,
    segment: str | None = None,
    limit: int | None = 30,
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []

    if metric:
        conditions.append("metric ILIKE %s")
        params.append(f"%{metric}%")
    if annee_reference:
        conditions.append("annee_reference = %s")
        params.append(annee_reference)
    if perimetre:
        conditions.append("perimetre ILIKE %s")
        params.append(f"%{perimetre}%")
    if statistique:
        conditions.append("statistique = %s")
        params.append(statistique)
    if nature_revenu:
        conditions.append("nature_revenu = %s")
        params.append(nature_revenu)
    if segment:
        conditions.append("segment ILIKE %s")
        params.append(f"%{segment}%")

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    limit_clause = "LIMIT %s" if limit else ""
    if limit:
        params.append(limit)

    # DISTINCT : une même table réingérée (ou réextraite par le LLM) produit
    # des lignes strictement identiques dans `facts` ; on ne veut pas les
    # répéter dans la réponse. `d.title`/`d.source` sont aliasés pour ne pas
    # écraser silencieusement `f.source` (la source du fait lui-même, exigée
    # par CLAUDE.md §3) lors du zip colonnes -> dict.
    sql = f"""
        SELECT DISTINCT
            f.metric, f.value, f.unit, f.annee_reference, f.perimetre,
            f.segment, f.statistique, f.nature_revenu, f.source, f.fiabilite,
            f.doc_id, d.title AS doc_title, d.source AS doc_source
        FROM facts f
        JOIN documents d USING (doc_id)
        {where}
        ORDER BY f.annee_reference DESC
        {limit_clause}
    """

    with psycopg.connect(settings.rag_db_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d.name for d in cur.description]  # type: ignore[union-attr]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_series_breaks(concept: str | None = None) -> list[dict[str, Any]]:
    with psycopg.connect(settings.rag_db_dsn) as conn:
        with conn.cursor() as cur:
            if concept:
                cur.execute(
                    "SELECT * FROM series_breaks WHERE concept ILIKE %s",
                    (f"%{concept}%",),
                )
            else:
                cur.execute("SELECT * FROM series_breaks")
            cols = [d.name for d in cur.description]  # type: ignore[union-attr]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
