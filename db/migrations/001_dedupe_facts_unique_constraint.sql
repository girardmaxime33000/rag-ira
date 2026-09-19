-- Purge les doublons existants dans `facts` puis applique la contrainte
-- UNIQUE désormais posée dans db/schema.sql (voir commit fix: facts non
-- filtrées et avertissements de rupture dupliqués).
--
-- Idempotent : peut être rejoué sans risque si déjà appliqué.
--
-- Usage :
--   psql "$RAG_DB_DSN" -f db/migrations/001_dedupe_facts_unique_constraint.sql
-- ou, avec la stack Docker du dépôt (docker-compose.yml racine) :
--   docker compose exec -T postgres psql -U rag -d rag < db/migrations/001_dedupe_facts_unique_constraint.sql

BEGIN;

-- 1. Purge des doublons : on garde la ligne de plus petit fact_id pour
--    chaque combinaison de clé naturelle, on supprime le reste.
DELETE FROM facts f
USING (
    SELECT
        MIN(fact_id) AS keep_id,
        doc_id, metric, value, unit, annee_reference, perimetre,
        segment, statistique, nature_revenu, source
    FROM facts
    GROUP BY
        doc_id, metric, value, unit, annee_reference, perimetre,
        segment, statistique, nature_revenu, source
    HAVING COUNT(*) > 1
) dupes
WHERE f.doc_id = dupes.doc_id
  AND f.metric = dupes.metric
  AND f.value = dupes.value
  AND f.unit = dupes.unit
  AND f.annee_reference = dupes.annee_reference
  AND f.perimetre = dupes.perimetre
  AND f.segment = dupes.segment
  AND f.statistique = dupes.statistique
  AND f.nature_revenu = dupes.nature_revenu
  AND f.source = dupes.source
  AND f.fact_id <> dupes.keep_id;

-- 2. Contrainte d'unicité (no-op si déjà posée par un schema.sql à jour).
--    PostgreSQL n'a pas de `ADD CONSTRAINT IF NOT EXISTS` : on vérifie via
--    pg_constraint pour rester idempotent.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'facts_natural_key_unique'
    ) THEN
        ALTER TABLE facts
            ADD CONSTRAINT facts_natural_key_unique
            UNIQUE (doc_id, metric, value, unit, annee_reference, perimetre, segment, statistique, nature_revenu, source);
    END IF;
END $$;

COMMIT;
