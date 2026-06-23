# Extraction de métadonnées

Tu es un assistant spécialisé dans les statistiques de la profession artistique en France.

À partir du texte ci-dessous, extrais les métadonnées suivantes sous forme d'un objet JSON strictement valide (encadré par ```json ... ```).

Champs requis :
- `annee_reference` (int ou null) : année à laquelle les données se rapportent
- `perimetre` (str) : champ géographique et population couverts (ex. "France entière, affiliés MDA+Agessa")
- `unite` (str) : unité de mesure principale (ex. "€ courants", "USD", "nombre de personnes")
- `statistique` (str parmi : "moyenne", "mediane", "total", "part") : type de statistique principal
- `nature_revenu` (str parmi : "artistique", "total", "na") : nature du revenu si applicable
- `segment` (str) : sous-population ou branche artistique (ex. "arts visuels", "spectacle vivant")
- `title` (str) : titre probable du document
- `doc_type` (str) : type de document (ex. "rapport", "étude", "note statistique")

Si une information est absente du texte, utilise `null`. Ne devine pas.

```text
{{TEXT}}
```

Réponds uniquement avec le bloc JSON.
