from dataclasses import dataclass
from docling.datamodel.document import DoclingDocument
from docling_core.types.doc import TableItem, TextItem


@dataclass
class RoutedContent:
    narrative_chunks: list[str]
    """Text-only content safe for vector embedding."""
    raw_tables: list[TableItem]
    """Tables to be parsed into structured facts — never embedded."""
    doc: DoclingDocument
    """Source document, needed to export tables with full context."""


def route_document(doc: DoclingDocument) -> RoutedContent:
    narrative: list[str] = []
    tables: list[TableItem] = []

    for item, _ in doc.iterate_items():
        if isinstance(item, TableItem):
            tables.append(item)
        elif isinstance(item, TextItem):
            text = item.text.strip()
            if text:
                narrative.append(text)

    return RoutedContent(narrative_chunks=narrative, raw_tables=tables, doc=doc)
