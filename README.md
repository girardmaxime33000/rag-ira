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

## Installation

```bash
git clone https://github.com/girardmaxime33000/rag-ira.git
cd rag-ira
cp .env.example .env
make setup   # uv sync + ollama pull qwen3:4b et bge-m3
```

### Dépendances OCR

Docling utilise `rapidocr-onnxruntime` comme backend OCR. Assure-toi que les deux sont dans le venv :

```bash
uv add rapidocr-onnxruntime onnxruntime
```

> L'avertissement HuggingFace `unauthenticated requests` au premier lancement est normal — les modèles se téléchargent sans token. Tu peux définir `HF_TOKEN` dans `.env` pour accélérer les téléchargements ultérieurs.

## Démarrage rapide

```bash
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
# Déposer les PDFs dans data/raw/, puis ingérer tous les documents
find data/raw -name "*.pdf" -print0 | xargs -0 -I{} uv run python -m src.cli ingest "{}"

# Ou un seul fichier
make ingest FILE="data/raw/mon_rapport.pdf"

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
    convert.py              Docling PDF → DoclingDocument (OCR via rapidocr-onnxruntime)
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

## Corpus (`data/raw/`)

> Fichiers gitignorés — à placer manuellement dans `data/raw/` après clonage.

### Statut juridique et textes réglementaires

| Fichier | Description |
|---|---|
| `Article L382-1 - Code de la sécurité sociale - Légifrance.pdf` | Article fondateur du régime social des artistes-auteurs |
| `Loi n° 75-1348 du 31 décembre 1975 …pdf` | Loi instituant la sécurité sociale des artistes-auteurs |
| `Décret n° 2020-1095 du 28 août 2020.pdf` | Décret réforme Urssaf 2020 |
| `Légifrance - lois 64-1338.pdf` | Loi 64-1338 |
| `rapports Sénat L25-206.pdf` | Rapport sénatorial |

### Statistiques artistes-auteurs (DEPS / ministère de la Culture)

| Fichier | Description |
|---|---|
| `Observatoire des revenus 2019-2021.pdf` | Observatoire des revenus des artistes-auteurs 2019–2021 |
| `Culture Etudes 2025-6.pdf` | Culture Études 2025-6 |
| `Culture Études 2022-2.pdf` | Culture Études 2022-2 |
| `DEPS Culture Chiffres 2024-1.pdf` | DEPS Culture Chiffres 2024-1 |
| `cartographie des statistiques culturelles 2025-20.pdf` | Cartographie des statistiques culturelles 2025 |
| `Bilan annuel 2025.pdf` | Bilan annuel 2025 |
| `rapport_ Racine2020.pdf` | Rapport Racine 2020 — L'auteur et l'acte de création |
| `Nomenclature_4Nemboites_PCS2003.xls` | Nomenclature PCS 2003 |
| `Nomenclature_4Nemboites_PCS2020.xlsx` | Nomenclature PCS 2020 |

### Marché de l'art contemporain — Artprice (rapports annuels)

| Fichier | Période |
|---|---|
| `report artprice trends2002.pdf` … `report artprice trends2025_en.pdf` | 2002–2025 (séries annuelles, en anglais) |
| `artprice-contemporary-2011-2012-en.pdf` | 2011–2012 |
| `artprice-contemporary-2012-2013-en.pdf` | 2012–2013 |
| `artprice-contemporary-2013-2014-en.pdf` | 2013–2014 |
| `marché de l'art contemporain 2006:2007.pdf` … `marché de l'art contemporain 20010:2011.pdf` | 2006–2011 (en français) |
| `the-contemporary-art-market-report-2019.pdf` … `the-contemporary-art-market-report-2025.pdf` | 2019–2025 |

### Marché de l'art — Art Basel / UBS

| Fichier | Description |
|---|---|
| `The-Art-Basel-and-UBS-Art-Market-Report-_2021.pdf` | Art Market Report 2021 |
| `The-Art-Basel-and-UBS-Art-Market-Report-2025.pdf` | Art Market Report 2025 |
| `Contemporary art market 2009:2010.pdf` | Rapport marché 2009–2010 |

---

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
