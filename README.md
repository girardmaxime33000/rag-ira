# RAG-IRA

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![Ollama](https://img.shields.io/badge/Ollama-qwen3%3A4b%20%7C%20bge--m3-black?logo=ollama)
![Postgres](https://img.shields.io/badge/Postgres-16%20%2B%20pgvector-336791?logo=postgresql)
![Langfuse](https://img.shields.io/badge/Observabilité-Langfuse-orange)
![Licence](https://img.shields.io/badge/Licence-MIT-green)
![100% local](https://img.shields.io/badge/Cloud-0%25-brightgreen)

> **RAG 100 % local sur les statistiques de la profession artistique en France.**
> Interroge un corpus de rapports officiels, d'études sectorielles et de données de marché
> sans envoyer une seule donnée à un service cloud.

---

## Table des matières

- [Pourquoi ce projet ?](#pourquoi-ce-projet-)
- [Architecture](#architecture)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Démarrage rapide](#démarrage-rapide)
- [Utilisation](#utilisation)
- [Corpus](#corpus-dataraw)
- [Schéma de la base de données](#schéma-de-la-base-de-données)
- [Garde-fous de génération](#garde-fous-de-génération)
- [Limitations connues](#limitations-connues)
- [Invariantes techniques](#invariantes-techniques)
- [Contributing](#contributing)

---

## Pourquoi ce projet ?

Les statistiques sur la profession artistique en France sont éparpillées dans des dizaines de rapports hétérogènes — DEPS, Urssaf, Artprice, Art Basel, rapports parlementaires — avec des **ruptures de série documentées**, des périmètres incomparables et des unités mélangées (€ courants, € constants, USD). Un LLM classique ne connaît pas ces données récentes et ne peut pas alerter sur les pièges statistiques.

Ce projet construit un RAG local qui :

- **Ingère** ces documents via Docling (extraction de texte et de tableaux)
- **Sépare** strictement les tableaux chiffrés (→ SQL) du texte narratif (→ vecteurs)
- **Répond** aux questions en citant systématiquement source, année et périmètre
- **Avertit** automatiquement quand une comparaison temporelle traverse une rupture de série
- **Trace** chaque appel dans Langfuse pour évaluation et audit

Tout tourne en local sur macOS Apple Silicon (Metal) — aucune donnée ne quitte la machine.

### Cas d'usage

| Cas d'usage | Description |
|---|---|
| **Veille réglementaire** | Interroger le corpus juridique (lois, décrets, rapports sénat) pour comprendre l'évolution du statut social des artistes-auteurs depuis 1964 |
| **Analyse de revenus** | Comparer les revenus artistiques et totaux par segment (arts visuels, spectacle vivant, livre…) sur plusieurs années, avec alertes sur les ruptures de série |
| **Suivi du marché de l'art** | Analyser les tendances du marché de l'art contemporain (volumes, prix, parts de marché par pays) à partir des rapports Artprice et Art Basel 2002–2025 |
| **Production de notes de synthèse** | Générer des synthèses thématiques sourcées sur un sujet précis (ex. : évolution des effectifs, poids économique de la culture, comparaison France/monde) |
| **Préparation d'arguments** | Préparer des argumentaires chiffrés et sourcés pour des rapports, prises de parole ou dossiers de financement |
| **Détection de pièges statistiques** | Identifier automatiquement les comparaisons hasardeuses (changement de périmètre, confusion moyenne/médiane, mélange €/USD) |

### Types de documentation générables

- **Fiches de synthèse** par segment artistique ou par période, avec sources et périmètres explicites
- **Chronologies chiffrées** des effectifs ou revenus sur longue période, avec signalement des ruptures de série
- **Notes de positionnement** comparant la France à d'autres marchés (UK, USA, Chine) sur le marché de l'art
- **Rapports d'évolution** du cadre réglementaire (MDA → Agessa → Urssaf) et de ses impacts statistiques
- **Tableaux de bord** exportables à partir des données structurées de la table `facts`

### APIs à intégrer (roadmap)

Le corpus statique (PDFs) a vocation à être complété par des flux de données en temps réel. Les intégrations prioritaires identifiées :

| API / Source | Données disponibles | Intérêt |
|---|---|---|
| **Urssaf** — API Déclaratif | Cotisants artistes-auteurs, revenus déclarés, effectifs par secteur | Mise à jour annuelle des données de référence post-2020 |
| **data.gouv.fr** | Jeux de données ouverts culture, emploi, fiscalité | Accès aux fichiers DEPS, Observatoire des revenus, nomenclatures PCS |
| **INSEE** — API Données | Séries longues emploi culturel, revenus, PCS | Contextualisation macroéconomique et comparaisons sectorielles |
| **data.culture.gouv.fr** | Données ouvertes du Ministère de la Culture | Statistiques officielles DEPS, subventions, établissements culturels |
| **Banque de France** | Taux de change €/USD historiques | Conversion fiable pour comparaisons internationales |

---

## Architecture

```
PDF
 └─► Docling (TableFormer ACCURATE)
       ├─► TextItem  ──► embed (bge-m3, 1024d) ──► pgvector  (table chunks)
       └─► TableItem ──────────────────────────► SQL         (table facts)
                                                      │
                          ┌───────────────────────────┘
                          ▼
              Question utilisateur
                    │
                    ▼
              router.py  ──classify──►  qualitative  ──► vector.py
                                    ►  quantitative  ──► structured.py
                                    ►  hybride       ──► les deux
                    │
                    ▼
         Contexte assemblé (chunks + facts + series_breaks)
                    │
                    ▼
         qwen3:4b (Ollama) + prompts/generation.md
                    │
                    ▼
         Réponse annotée (source | année | périmètre)
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
   Langfuse (traces)    src/api/openai_compat.py (/v1/chat/completions)
                                │
                                ▼
                         Open WebUI (Docker, :3001)
```

---

## Prérequis

| Outil | Version | Rôle |
|---|---|---|
| macOS Apple Silicon | — | Accélération Metal pour Ollama |
| [Ollama](https://ollama.ai) | ≥ 0.6 | LLM + embeddings en local |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | ≥ 4.x | Postgres/pgvector + Langfuse |
| Python | 3.12 | Runtime applicatif |
| [uv](https://docs.astral.sh/uv/) | ≥ 0.4 | Gestion des dépendances Python |

---

## Installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/girardmaxime33000/rag-ira.git
cd rag-ira
```

### 2. Configurer l'environnement

```bash
cp .env.example .env
```

Édite `.env` et renseigne tes clés Langfuse (voir [Démarrage rapide](#démarrage-rapide)) :

```env
OLLAMA_HOST=http://localhost:11434
OLLAMA_LLM_MODEL=qwen3:4b
OLLAMA_EMBED_MODEL=bge-m3
EMBED_DIM=1024
RAG_DB_DSN=postgresql://rag:rag@localhost:5432/rag
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

### 3. Installer les dépendances Python

```bash
make setup
# équivalent à : uv sync + ollama pull qwen3:4b + ollama pull bge-m3
```

### 4. Dépendances OCR

Docling utilise `rapidocr-onnxruntime` comme backend OCR :

```bash
uv add rapidocr-onnxruntime onnxruntime
```

> **Note :** L'avertissement `unauthenticated requests to HF Hub` au premier lancement est normal.
> Les modèles Docling (TableFormer, layout) se téléchargent automatiquement depuis HuggingFace.
> Définis `HF_TOKEN` dans `.env` pour accélérer les téléchargements ultérieurs.

---

## Démarrage rapide

### Infrastructure RAG (Postgres + pgvector)

```bash
make up
# démarre Postgres 16 + pgvector sur localhost:5432
# applique db/schema.sql et db/seed_series_breaks.sql automatiquement
```

### Langfuse (observabilité)

Langfuse tourne dans une **stack Docker séparée** (Postgres, ClickHouse, Redis, MinIO) :

```bash
# 1. Éditer les secrets dans third_party/langfuse/docker-compose.yml (chercher # CHANGEME)
# 2. Démarrer
make langfuse-up
# Interface disponible sur http://localhost:3000
```

1. Ouvre [http://localhost:3000](http://localhost:3000) — crée ton compte (premier compte = admin)
2. Crée un projet → **Settings → API Keys** → génère une paire de clés
3. Colle les clés dans `.env`

### Open WebUI (interface de chat)

Open WebUI se branche sur le pipeline RAG complet via un shim local compatible OpenAI —
il ne parle jamais directement à Ollama (voir [CLAUDE.md §8](CLAUDE.md#8-interface-open-webui)).

```bash
# 1. Démarrer le serveur compatible OpenAI côté hôte
make api
# → http://localhost:8000/v1

# 2. Démarrer Open WebUI (stack Docker séparée)
make webui-up
# → http://localhost:3001
```

Dans Open WebUI, le modèle `rag-ira` est automatiquement disponible dans le sélecteur —
chaque message déclenche le routage retrieval → facts/chunks → génération, avec les
sources et avertissements de rupture de série affichés en pied de réponse.

---

## Utilisation

### Ingestion de documents

```bash
# Déposer les PDFs dans data/raw/, puis ingérer (gère les espaces dans les noms)
find data/raw -name "*.pdf" -print0 | xargs -0 -I{} uv run python -m src.cli ingest "{}"

# Ingérer un fichier unique
make ingest FILE="data/raw/mon_rapport.pdf"
```

L'ingestion :
1. Convertit le PDF via Docling (OCR si nécessaire)
2. Sépare texte narratif → `chunks` et tableaux → `facts` (invariante stricte)
3. Extrait les métadonnées via le LLM (année, périmètre, unité…)
4. Calcule les embeddings bge-m3 et stocke dans Postgres

### Interrogation

```bash
make query Q="Quel est le revenu médian des artistes-auteurs en 2022 ?"
make query Q="Comment a évolué le marché de l'art contemporain entre 2010 et 2023 ?"
make query Q="Quelle est la part de Paris dans le marché de l'art mondial ?"
```

### Évaluation

```bash
make eval
# Lance les 5 questions-pièges du golden dataset
# Score via LLM-as-judge (Ollama) + résultats dans Langfuse
# Exit 1 si un piège n'est pas détecté
```

### Développement

```bash
make test   # pytest
make lint   # ruff + mypy
```

---

## Corpus (`data/raw/`)

> Les fichiers sont **gitignorés** — à placer manuellement dans `data/raw/` après clonage.

### Textes réglementaires et législatifs

| Fichier | Contenu | Langue | Année |
|---|---|---|---|
| `Article L382-1 - Code de la sécurité sociale…pdf` | Article fondateur du régime social des artistes-auteurs | FR | — |
| `Loi n° 75-1348 du 31 décembre 1975…pdf` | Loi instituant la sécurité sociale des artistes-auteurs | FR | 1975 |
| `Décret n° 2020-1095 du 28 août 2020.pdf` | Réforme du recouvrement des cotisations (transfert Urssaf) | FR | 2020 |
| `Légifrance - lois 64-1338.pdf` | Loi 64-1338 | FR | 1964 |
| `rapports Sénat L25-206.pdf` | Rapport sénatorial sur le statut des artistes-auteurs | FR | 2025 |
| `rapport_ Racine2020.pdf` | Rapport Racine — L'auteur et l'acte de création | FR | 2020 |

### Statistiques officielles (DEPS / Ministère de la Culture)

| Fichier | Contenu | Langue | Période |
|---|---|---|---|
| `Observatoire des revenus 2019-2021.pdf` | Revenus des artistes-auteurs (Urssaf) | FR | 2019–2021 |
| `Culture Etudes 2025-6.pdf` | Étude DEPS 2025-6 | FR | 2025 |
| `Culture Études 2022-2.pdf` | Étude DEPS 2022-2 | FR | 2022 |
| `DEPS Culture Chiffres 2024-1.pdf` | Chiffres clés de la culture 2024 | FR | 2024 |
| `cartographie des statistiques culturelles 2025-20.pdf` | Cartographie des sources statistiques culturelles | FR | 2025 |
| `Bilan annuel 2025.pdf` | Bilan annuel Urssaf artistes-auteurs | FR | 2025 |
| `Nomenclature_4Nemboites_PCS2003.xls` | Nomenclature PCS 2003 | FR | 2003 |
| `Nomenclature_4Nemboites_PCS2020.xlsx` | Nomenclature PCS 2020 | FR | 2020 |

### Marché de l'art — Artprice (rapports annuels)

| Fichier | Langue | Période |
|---|---|---|
| `report artprice trends2002.pdf` → `report artprice trends2025_en.pdf` | EN | 2002–2025 |
| `artprice-contemporary-2011-2012-en.pdf` | EN | 2011–2012 |
| `artprice-contemporary-2012-2013-en.pdf` | EN | 2012–2013 |
| `artprice-contemporary-2013-2014-en.pdf` | EN | 2013–2014 |
| `marché de l'art contemporain 2006:2007.pdf` → `marché de l'art contemporain 20010:2011.pdf` | FR | 2006–2011 |
| `the-contemporary-art-market-report-2019.pdf` → `the-contemporary-art-market-report-2025.pdf` | EN | 2019–2025 |

### Marché de l'art — Art Basel / UBS

| Fichier | Langue | Année |
|---|---|---|
| `Contemporary art market 2009:2010.pdf` | EN | 2009–2010 |
| `The-Art-Basel-and-UBS-Art-Market-Report-_2021.pdf` | EN | 2021 |
| `The-Art-Basel-and-UBS-Art-Market-Report-2025.pdf` | EN | 2025 |

---

## Schéma de la base de données

```
documents
├── doc_id          PK
├── title           TEXT
├── source          TEXT
├── doc_type        TEXT          (rapport, étude, loi, décret…)
├── annee_publication INT
├── path            TEXT
└── sha256          TEXT UNIQUE

chunks                            ← texte narratif uniquement
├── chunk_id        PK
├── doc_id          FK → documents
├── text            TEXT
├── embedding       vector(1024)  ← index HNSW (cosine)
└── metadata        JSONB         ← index GIN

facts                             ← tableaux chiffrés uniquement
├── fact_id         PK
├── doc_id          FK → documents
├── metric          TEXT          (ex. effectif_declarants)
├── value           NUMERIC
├── unit            TEXT          (€ courants, USD, nombre…)
├── annee_reference INT           ← année des données, ≠ année de publication
├── perimetre       TEXT          (ex. France entière, affiliés MDA+Agessa ≤2018)
├── segment         TEXT          (arts visuels, spectacle vivant…)
├── statistique     ENUM          (moyenne | mediane | total | part)
├── nature_revenu   ENUM          (artistique | total | na)
├── source          TEXT
└── fiabilite       TEXT

series_breaks                     ← ruptures de série documentées
├── id              PK
├── concept         TEXT
├── periode_avant   TEXT
├── periode_apres   TEXT
├── regle           TEXT
└── avertissement   TEXT          ← affiché automatiquement en cas de comparaison
```

**Ruptures de série pré-chargées :**

| Concept | Avant | Après | Impact |
|---|---|---|---|
| Effectifs artistes-auteurs | ≤ 2018 (MDA+Agessa, affiliés/assujettis) | ≥ 2020 (Urssaf, affiliation dès le 1er euro) | Périmètres non comparables |
| Recouvrement cotisations | MDA/Agessa | Urssaf Limousin (2019) | Source administrative différente |

---

## Garde-fous de génération

Le prompt `prompts/generation.md` impose les règles suivantes pour chaque réponse :

| Règle | Description |
|---|---|
| **Citation obligatoire** | Chaque chiffre → `[source \| année_référence \| périmètre]` |
| **Ruptures de série** | Avertissement complet avant toute comparaison cross-rupture |
| **Revenu artistique ≠ total** | ~67 % des artistes-auteurs ont un revenu complémentaire |
| **Moyenne ≠ médiane** | Distributions très asymétriques — toujours préciser lequel |
| **€ ≠ USD** | Aucune conversion sans source explicite |
| **Ambiguïté "part de marché"** | Part de Paris dans le marché de l'art (USD) ≠ part de la culture dans le PIB (€) |

---

## Limitations connues

- **Tableaux non parsés automatiquement** : les tableaux détectés par Docling sont signalés (`⚠️ N tableau(x) détecté(s)`) mais leur insertion dans `facts` nécessite un parseur métier à implémenter par document.
- **Documents scannés** : l'OCR (RapidOCR onnxruntime) peut retourner des résultats vides sur des pages très dégradées ou en écriture manuscrite. Ces pages sont ignorées silencieusement.
- **Extraction LLM de métadonnées** : l'extraction automatique via qwen3:4b peut être incomplète — des fallbacks (`"rapport"`, nom du fichier) s'appliquent automatiquement.
- **Corpus anglophone** : les documents Artprice et Art Basel sont en anglais ; les embeddings bge-m3 sont multilingues mais les requêtes en français peuvent avoir un score de similarité légèrement plus faible sur ces documents.
- **Facts vides** : sans parseur de tableaux dédié, la table `facts` reste vide et les requêtes quantitatives n'ont pas de données chiffrées structurées.

---


## Structure du projet

```
.
├── config/settings.py              Configuration typée (pydantic-settings)
├── db/
│   ├── schema.sql                  Schéma Postgres (4 tables + enums + index)
│   └── seed_series_breaks.sql      Ruptures de série pré-chargées
├── prompts/
│   ├── metadata_extraction.md      Prompt extraction de métadonnées
│   └── generation.md               Prompt de génération avec garde-fous
├── src/
│   ├── observability/tracing.py    Décorateur @observe → Langfuse
│   ├── ingestion/
│   │   ├── convert.py              Docling PDF → DoclingDocument
│   │   ├── route.py                Sépare TextItem et TableItem (invariante stricte)
│   │   ├── metadata.py             Extraction métadonnées (heuristique + LLM)
│   │   └── load.py                 Écriture Postgres via psycopg
│   ├── embeddings/embedder.py      Ollama bge-m3, vérifie dim=1024
│   ├── retrieval/
│   │   ├── vector.py               Recherche pgvector + filtres JSONB
│   │   ├── structured.py           Requêtes SQL sur facts + series_breaks
│   │   └── router.py               Classifie la requête → bon backend
│   ├── generation/
│   │   ├── llm.py                  Ollama qwen3:4b, tracé Langfuse
│   │   └── answer.py               Assemblage contexte + prompt
│   ├── api/openai_compat.py        Shim /v1/chat/completions (pour Open WebUI)
│   └── cli.py                      Typer : ingest | query | eval | serve
├── eval/
│   ├── golden_dataset.jsonl        5 questions-pièges
│   └── run_eval.py                 LLM-as-judge (Ollama) + log Langfuse
├── tests/test_ingestion.py         Tests unitaires (5 tests)
├── third_party/
│   ├── langfuse/                   Compose officiel Langfuse self-hosted
│   └── open-webui/                 Compose Open WebUI (branché sur src/api)
├── data/
│   ├── raw/                        PDFs sources (gitignorés)
│   └── processed/                  Sorties intermédiaires (gitignorées)
├── docker-compose.yml              Stack RAG (Postgres+pgvector uniquement)
├── Makefile                        Commandes de référence
├── pyproject.toml                  Dépendances uv
└── CLAUDE.md                       Invariantes pour les sessions Claude
```

---

## Invariantes techniques

Voir [CLAUDE.md](CLAUDE.md) pour le détail complet.

| Invariante | Règle |
|---|---|
| **100 % local** | Zéro appel API cloud (pas d'OpenAI, Anthropic, Cohere, Voyage…) |
| **Tableaux jamais dans le vectoriel** | `TableItem` → `facts` SQL uniquement, jamais dans `chunks` |
| **Métadonnées obligatoires** | Tout fait chiffré porte `annee_reference`, `perimetre`, `unite`, `statistique`, `source` |
| **Ruptures de série** | Toute comparaison cross-rupture déclenche un avertissement |
| **Stack séparée** | RAG (`docker-compose.yml`), Langfuse et Open WebUI (`third_party/`) ne fusionnent jamais |
| **Pas de LangChain/LlamaIndex** | Bibliothèques directes uniquement |
| **Open WebUI = shim local** | `src/api/openai_compat.py` mime le format OpenAI mais route vers Ollama en local, jamais openai.com |

---

## Contributing

### Conventions

- **Python 3.12**, formaté avec `ruff`, typé avec `mypy`
- Pas de commentaires évidents — seulement les contraintes non-triviales
- Pas de LangChain, LlamaIndex, ni aucun framework d'orchestration LLM
- Toute modification du schéma SQL → mettre à jour `db/schema.sql` et ce README

### Ajouter un document au corpus

1. Dépose le PDF dans `data/raw/`
2. Lance `make ingest FILE="data/raw/ton_fichier.pdf"`
3. Si le document contient des tableaux chiffrés importants, implémente un parseur dédié qui insère dans `facts` avec tous les champs obligatoires

### Ajouter une rupture de série

```sql
INSERT INTO series_breaks (concept, periode_avant, periode_apres, regle, avertissement)
VALUES ('Nouveau concept', 'Avant ...', 'Après ...', 'Règle de non-comparaison', 'Avertissement affiché à l''utilisateur');
```

Puis documente-la dans `CLAUDE.md` section 4.

### Lancer les tests

```bash
make test   # 5 tests unitaires
make lint   # ruff check + mypy
```
