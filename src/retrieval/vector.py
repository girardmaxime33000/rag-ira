from typing import Any

import psycopg
import psycopg.types.json

from config.settings import settings
from src.embeddings.embedder import embed


def search(
    query: str,
    *,
    top_k: int = 5,
    metadata_filter: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    vector = embed(query)

    filter_clause = ""
    params: list[Any] = [str(vector), top_k]

    if metadata_filter:
        conditions = []
        for key, val in metadata_filter.items():
            conditions.append(f"metadata @> %s::jsonb")
            params.insert(-1, psycopg.types.json.Jsonb({key: val}))
        filter_clause = "WHERE " + " AND ".join(conditions)
        # Reorder: vector param first, then filters, then top_k
        params = [str(vector)] + params[1:-1] + [top_k]

    sql = f"""
        SELECT chunk_id, doc_id, text, metadata,
               1 - (embedding <=> %s::vector) AS score
        FROM chunks
        {filter_clause}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    params = [str(vector)] + (params[1:-1] if metadata_filter else []) + [str(vector), top_k]

    with psycopg.connect(settings.rag_db_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d.name for d in cur.description]  # type: ignore[union-attr]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
