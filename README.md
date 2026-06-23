# RAG-IRA — RAG local sur les statistiques de la profession artistique en France

RAG 100 % local sur un corpus de rapports et études sur la profession artistique en France
(artistes-auteurs, marché de l'art, poids économique de la culture).

## Architecture

```
PDF → Docling → route → texte narratif → embed (bge-m3) → pgvector (chunks)
                      → tableaux chiffrés → SQL (facts) ← jamais embeddés
                                                   ↓
                     Query → router → vector.py | structured.py
                                              ↓
                              qwen3:4b (Ollama) → réponse annotée
                                              ↓
                                         Langfuse (traces + eval)
```

## Prérequis

- macOS Apple Silicon (ou Linux x86)
- [Ollama](https://ollama.ai) installé sur l'hôte
- Docker Desktop (ou colima)
- Python 3.12 + [uv](https://docs.astral.sh/uv/)

## Démarrage rapide

```bash
cp .env.example .env
# Éditez .env si nécessaire (clés Langfuse après setup)

make setup       # uv sync + pull modèles Ollama (qwen3:4b, bge-m3)
make up          # démarre Postgres+pgvector sur :5432
```

### Langfuse (observabilité — optionnel mais recommandé)

Langfuse tourne dans sa propre stack Docker, **séparée** de celle du RAG.
Elle embarque Postgres, ClickHouse, Redis et MinIO.

```bash
# Éditer les secrets dans third_party/langfuse/docker-compose.yml (chercher # CHANGEME)
make langfuse-up   # démarre Langfuse sur http://localhost:3000
```

Créez un projet dans l'UI Langfuse, copiez les clés dans `.env` :
```
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

## Utilisation

```bash
# Ingérer un PDF
make ingest FILE=data/raw/rapport_mda_2022.pdf

# Poser une question
make query Q="Quel est le revenu médian des artistes-auteurs en 2022 ?"

# Lancer l'évaluation sur le golden dataset
make eval

# Tests et lint
make test
make lint
```

## Structure

```
config/settings.py          Configuration (pydantic-settings)
src/
  observability/tracing.py  Décorateur @observe → Langfuse
  ingestion/
    convert.py              Docling PDF → DoclingDocument
    route.py                Sépare texte (→ chunks) et tableaux (→ facts)
    metadata.py             Extraction métadonnées (règles + LLM)
    load.py                 Écriture Postgres via psycopg
  embeddings/embedder.py    Ollama bge-m3, vérifie dim=1024
  retrieval/
    vector.py               Recherche pgvector + filtres metadata
    structured.py           Requêtes SQL sur facts + series_breaks
    router.py               Classifie la requête → bon backend
  generation/
    llm.py                  Ollama qwen3:4b, tracé Langfuse
    answer.py               Assemble contexte + prompt + garde-fous
  cli.py                    Typer : ingest | query | eval
db/
  schema.sql                Schéma Postgres (documents, chunks, facts, series_breaks)
  seed_series_breaks.sql    Ruptures de série pré-chargées
prompts/
  metadata_extraction.md    Prompt extraction métadonnées
  generation.md             Prompt génération avec garde-fous
eval/
  golden_dataset.jsonl      5 questions-pièges
  run_eval.py               Évaluation LLM-as-judge (Ollama) + Langfuse
third_party/langfuse/       Compose officiel Langfuse (self-hosted)
```

## Garde-fous de génération

Le prompt `prompts/generation.md` impose :

1. Chaque chiffre cité → `[source | année_référence | périmètre]`
2. Comparaison temporelle → avertissement rupture de série si applicable
3. Revenu artistique ≠ revenu total (~67 % ont un revenu complémentaire)
4. Moyenne ≠ médiane (distributions très asymétriques)
5. € ≠ USD (pas de conversion sans source)
6. "Part de Paris dans le marché de l'art" (USD) ≠ "Part de la culture dans le PIB" (€)

## Invariantes techniques

Voir [CLAUDE.md](CLAUDE.md) pour les règles complètes imposées aux sessions Claude.

- **100 % local** : zéro appel API cloud
- **Tableaux jamais dans le vectoriel** : `TableItem` → `facts` SQL uniquement
- **Pas de LangChain/LlamaIndex** : bibliothèques directes uniquement
- **Deux stacks Docker séparées** : RAG (`docker-compose.yml`) et Langfuse (`third_party/langfuse/`)
