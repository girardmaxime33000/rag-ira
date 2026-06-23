# Invariantes de session — RAG statistiques artistiques France

Ce document est la source de vérité pour toute session Claude sur ce dépôt.
Respecter ces règles dans **tout** le code généré, sans exception.

## 1. 100 % local — zéro API cloud

- Génération et embeddings : **Ollama uniquement** (hôte, `http://localhost:11434`)
- Modèles : `qwen3:4b` (LLM) et `bge-m3` (embeddings, 1024 dim)
- **Interdit** : OpenAI, Anthropic, Voyage, Cohere, HuggingFace Inference API, ou toute autre API d'inférence externe

## 2. Tableaux chiffrés → jamais dans le vectoriel

- Les tableaux extraits par Docling (`TableItem`) vont **exclusivement** dans `facts` (SQL)
- Seul le texte narratif (`TextItem`) est embeddé dans `chunks`
- Cette invariante est **non négociable** et doit être vérifiée dans `src/ingestion/route.py`

## 3. Métadonnées de périmètre obligatoires

Tout enregistrement dans `facts` **doit** avoir :
- `annee_reference` (int) — année des données, pas de publication
- `perimetre` (str) — ex. "France entière, affiliés MDA+Agessa ≤2018"
- `unite` (str) — ex. "€ courants", "USD", "nombre de personnes"
- `statistique` (enum) — `moyenne | mediane | total | part`
- `nature_revenu` (enum) — `artistique | total | na`
- `source` (str)

Pas de chiffre sans ces cinq champs.

## 4. Ruptures de série à respecter

La table `series_breaks` contient les ruptures documentées.
Le pipeline de génération **doit** toujours interroger cette table et afficher l'avertissement
avant toute comparaison temporelle qui traverse une rupture.

Ruptures actuelles :
- **Effectifs artistes-auteurs** : ≤2018 (MDA+Agessa) vs ≥2020 (Urssaf, 1er euro) — périmètres non comparables
- **Recouvrement cotisations** : MDA/Agessa vs Urssaf Limousin (2019) — source administrative différente

## 5. Topologie de déploiement (macOS Apple Silicon)

| Composant | Où tourne | Adresse |
|---|---|---|
| Application Python | Hôte (Metal) | — |
| Ollama | Hôte (Metal) | `http://localhost:11434` |
| Postgres + pgvector (RAG) | Docker | `localhost:5432` |
| Langfuse (observabilité) | Docker séparé | `http://localhost:3000` |

Les deux `docker-compose.yml` sont **séparés** :
- RAG : `docker-compose.yml` (racine)
- Langfuse : `third_party/langfuse/docker-compose.yml`

**Ne jamais fusionner les deux composes.**

## 6. Stack verrouillée — pas de LangChain/LlamaIndex

Bibliothèques autorisées : `docling`, `ollama`, `psycopg`, `pgvector`, `langfuse`, `pydantic-settings`, `typer`, `python-dotenv`.

Toute suggestion d'ajouter LangChain, LlamaIndex, ou un framework d'orchestration LLM est à rejeter.

## 7. Commandes de référence

```bash
make setup      # uv sync + ollama pull des modèles
make up         # démarre Postgres+pgvector
make langfuse-up  # démarre Langfuse (stack séparée)
make ingest FILE=data/raw/mon_rapport.pdf
make query Q="Quel est le revenu médian des artistes-auteurs en 2022 ?"
make eval       # golden dataset via Langfuse
make test       # pytest
make lint       # ruff + mypy
```
