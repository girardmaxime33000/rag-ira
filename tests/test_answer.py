"""Tests purs (sans I/O) pour la déduplication du texte généré."""
from unittest.mock import patch

from src.generation.answer import _strip_echoed_reference_lines, answer


def test_strip_echoed_reference_lines_removes_raw_blocks():
    """Un petit modèle local recopie parfois tel quel le matériel de référence
    injecté dans le prompt (facts/ruptures), en plus de sa propre reformulation.
    Les lignes brutes dupliquées doivent être retirées, la reformulation gardée."""
    breaks_text = "⚠️ Effectifs artistes-auteurs : Périmètres non comparables."
    facts_text = "- prix_vente | 2025 | non précisé | total | 62160000 USD | source: x"

    response = (
        "Il existe une rupture de série sur les effectifs artistes-auteurs.\n"
        "⚠️ Effectifs artistes-auteurs : Périmètres non comparables.\n"
        "Faits chiffrés (`facts`) :\n"
        "* prix_vente | 2025 | non précisé | total | 62160000 USD | source: x"
    )

    result = _strip_echoed_reference_lines(response, facts_text, breaks_text)

    assert "⚠️" not in result
    assert "prix_vente" not in result
    assert "Il existe une rupture de série" in result


def test_strip_echoed_reference_lines_tolerates_near_verbatim_echo():
    """Cas réel observé en production : le modèle (temperature=0.1) reproduit
    l'avertissement quasi mot pour mot mais pas caractère pour caractère
    (guillemet typographique, point final en plus). Une égalité stricte de
    lignes rate ce cas ; le matching doit être tolérant à ces micro-écarts."""
    breaks_text = (
        "⚠️ Effectifs artistes-auteurs : Périmètres non comparables : "
        "changement de définition statistique en 2019-2020."
    )
    # Variante quasi identique : apostrophe typographique + espace en trop.
    response = (
        "Il existe une rupture de série à signaler.\n"
        "⚠️ Effectifs artistes-auteurs : Périmètres non comparables :  "
        "changement de définition statistique en 2019‑2020."
    )

    result = _strip_echoed_reference_lines(response, "", breaks_text)

    assert "Périmètres non comparables" not in result
    assert "Il existe une rupture de série à signaler." in result


def test_strip_echoed_reference_lines_keeps_own_prose():
    """Sans écho brut, la réponse du modèle ne doit pas être altérée."""
    response = "Le revenu médian est de 15 000 € [Urssaf | 2022 | France entière]."
    result = _strip_echoed_reference_lines(response, "- some fact line", "⚠️ some break")
    assert result == response


def test_answer_injects_full_coverage_not_truncated_facts_sample():
    """`query_facts()` ne renvoie qu'un échantillon récent (LIMIT + tri
    décroissant) : le prompt doit recevoir en plus un agrégat MIN/MAX fiable
    sur toute la table, pour que les questions de plage de données ne soient
    pas répondues seulement à partir de l'échantillon tronqué."""
    fake_context = {
        "query_type": "hybrid",
        "chunks": [],
        "facts": [
            {
                "metric": "prix_vente", "annee_reference": 2025,
                "perimetre": "non précisé", "statistique": "total",
                "value": 68320000, "unit": "USD", "source": "artprice",
            }
        ],
        "series_breaks": [],
        "coverage": {
            "annee_min": 2007, "annee_max": 2025,
            "nombre_facts": 1500, "annees_disponibles": [2007, 2025],
        },
    }

    with patch("src.generation.answer.retrieve", return_value=fake_context), \
         patch("src.generation.answer.generate") as mock_generate:
        mock_generate.return_value = "Réponse factice."
        result = answer("Quelle est la plage de données exploitable ?")

    sent_prompt = mock_generate.call_args[0][0]
    assert "2007" in sent_prompt and "2025" in sent_prompt
    assert result["sources"]["coverage"]["annee_min"] == 2007
