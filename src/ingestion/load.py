import hashlib
from pathlib import Path
from typing import Any

import psycopg

from config.settings import settings


def _conn() -> psycopg.Connection:
    return psycopg.connect(settings.rag_db_dsn)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def upsert_document(
    *,
    title: str,
    source: str,
    doc_type: str,
    annee_publication: int | None,
    path: Path,
    sha256: str,
) -> int:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (title, source, doc_type, annee_publication, path, sha256)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (sha256) DO UPDATE SET title = EXCLUDED.title
                RETURNING doc_id
                """,
                (title, source, doc_type, annee_publication, str(path), sha256),
            )
            row = cur.fetchone()
            assert row is not None
            return int(row[0])


def insert_chunk(
    *,
    doc_id: int,
    text: str,
    embedding: list[float],
    metadata: dict[str, Any],
) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chunks (doc_id, text, embedding, metadata)
                VALUES (%s, %s, %s::vector, %s)
                """,
                (doc_id, text, str(embedding), psycopg.types.json.Jsonb(metadata)),
            )


def insert_fact(
    *,
    doc_id: int,
    metric: str,
    value: float,
    unit: str,
    annee_reference: int,
    perimetre: str,
    segment: str,
    statistique: str,
    nature_revenu: str,
    source: str,
    fiabilite: str = "normale",
) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO facts
                  (doc_id, metric, value, unit, annee_reference, perimetre,
                   segment, statistique, nature_revenu, source, fiabilite)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (doc_id, metric, value, unit, annee_reference, perimetre,
                 segment, statistique, nature_revenu, source, fiabilite),
            )
