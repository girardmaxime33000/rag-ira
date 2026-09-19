"""Tests purs (sans I/O) pour la déduplication du texte généré."""
from src.generation.answer import _strip_echoed_reference_lines


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


def test_strip_echoed_reference_lines_keeps_own_prose():
    """Sans écho brut, la réponse du modèle ne doit pas être altérée."""
    response = "Le revenu médian est de 15 000 € [Urssaf | 2022 | France entière]."
    result = _strip_echoed_reference_lines(response, "- some fact line", "⚠️ some break")
    assert result == response
