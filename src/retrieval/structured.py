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
    sql = f"""
        SELECT f.*, d.title, d.source
        FROM facts f
        JOIN documents d USING (doc_id)
        {where}
        ORDER BY annee_reference DESC
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
