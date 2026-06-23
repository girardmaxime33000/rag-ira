CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    doc_id      SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    source      TEXT NOT NULL,
    doc_type    TEXT NOT NULL,
    annee_publication INT,
    path        TEXT NOT NULL,
    sha256      TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id    SERIAL PRIMARY KEY,
    doc_id      INT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    text        TEXT NOT NULL,
    embedding   vector(1024),
    metadata    JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS chunks_metadata_gin
    ON chunks USING gin (metadata);

CREATE TYPE statistique_type AS ENUM ('moyenne', 'mediane', 'total', 'part');
CREATE TYPE nature_revenu_type AS ENUM ('artistique', 'total', 'na');

CREATE TABLE IF NOT EXISTS facts (
    fact_id         SERIAL PRIMARY KEY,
    doc_id          INT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    metric          TEXT NOT NULL,
    value           NUMERIC NOT NULL,
    unit            TEXT NOT NULL,
    annee_reference INT NOT NULL,
    perimetre       TEXT NOT NULL,
    segment         TEXT NOT NULL DEFAULT '',
    statistique     statistique_type NOT NULL,
    nature_revenu   nature_revenu_type NOT NULL DEFAULT 'na',
    source          TEXT NOT NULL,
    fiabilite       TEXT NOT NULL DEFAULT 'normale'
);

CREATE TABLE IF NOT EXISTS series_breaks (
    id              SERIAL PRIMARY KEY,
    concept         TEXT NOT NULL,
    periode_avant   TEXT NOT NULL,
    periode_apres   TEXT NOT NULL,
    regle           TEXT,
    avertissement   TEXT NOT NULL
);
