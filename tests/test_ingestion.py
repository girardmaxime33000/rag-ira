"""Stub tests — verify module imports and core invariants without I/O."""
import importlib
import sys
from unittest.mock import MagicMock, patch


def test_embedder_dim_check():
    """Embedder must raise if Ollama returns wrong dimension."""
    with patch("ollama.embeddings", return_value={"embedding": [0.0] * 512}):
        from src.embeddings.embedder import embed

        try:
            embed("test")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "1024" in str(e)


def test_embedder_correct_dim():
    with patch("ollama.embeddings", return_value={"embedding": [0.1] * 1024}):
        # Reimport to avoid cached bad result
        import importlib
        import src.embeddings.embedder as mod
        importlib.reload(mod)
        result = mod.embed("test")
        assert len(result) == 1024


def test_route_document_no_table_in_chunks():
    """Tables must never appear in narrative_chunks."""
    from docling_core.types.doc import TableItem, TextItem, DocItem
    from unittest.mock import MagicMock

    mock_doc = MagicMock()

    text_item = MagicMock(spec=TextItem)
    text_item.text = "Ceci est un texte narratif."

    table_item = MagicMock(spec=TableItem)

    mock_doc.iterate_items.return_value = [
        (text_item, None),
        (table_item, None),
    ]

    from src.ingestion.route import route_document, RoutedContent
    result = route_document(mock_doc)

    assert isinstance(result, RoutedContent)
    # Tables go to raw_tables, not narrative
    assert len(result.raw_tables) == 1
    assert len(result.narrative_chunks) == 1
    assert "texte narratif" in result.narrative_chunks[0]


def test_settings_loads():
    from config.settings import settings
    assert settings.embed_dim == 1024
    assert "localhost" in settings.ollama_host


def test_classify_query_types():
    from src.retrieval.router import classify, QueryType

    assert classify("Raconte-moi l'histoire du statut d'artiste") == QueryType.QUALITATIVE
    assert classify("Combien d'artistes déclarent un revenu moyen en 2022 ?") == QueryType.QUANTITATIVE
