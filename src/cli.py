from pathlib import Path

import typer

app = typer.Typer(help="RAG local — statistiques de la profession artistique en France")


@app.command()
def ingest(path: Path = typer.Argument(..., help="Chemin vers un fichier PDF à ingérer")) -> None:
    """Ingère un document PDF : parse, route, embed et stocke."""
    from src.ingestion.convert import convert_document
    from src.ingestion.route import route_document
    from src.ingestion.metadata import extract_from_filename, extract_with_llm
    from src.ingestion.load import upsert_document, insert_chunk, insert_fact, sha256_file
    from src.ingestion.table_parser import parse_tables
    from src.embeddings.embedder import embed

    if not path.exists():
        typer.echo(f"Fichier introuvable : {path}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Conversion de {path} …")
    doc = convert_document(path)
    routed = route_document(doc)

    file_meta = extract_from_filename(path)
    llm_meta: dict = {}
    if routed.narrative_chunks:
        typer.echo("Extraction des métadonnées via LLM …")
        llm_meta = extract_with_llm("\n".join(routed.narrative_chunks[:3]))

    sha = sha256_file(path)
    doc_id = upsert_document(
        title=llm_meta.get("title") or path.stem,
        source=file_meta["source"],
        doc_type=llm_meta.get("doc_type") or "rapport",
        annee_publication=file_meta.get("annee_publication"),
        path=path,
        sha256=sha,
    )

    typer.echo(f"Document enregistré (doc_id={doc_id}). Embedding de {len(routed.narrative_chunks)} chunks …")
    for text in routed.narrative_chunks:
        vector = embed(text)
        insert_chunk(
            doc_id=doc_id,
            text=text,
            embedding=vector,
            metadata=llm_meta,
        )

    if routed.raw_tables:
        typer.echo(f"Extraction de {len(routed.raw_tables)} tableau(x) → facts …")
        facts = parse_tables(
            routed.raw_tables,
            source=file_meta["source"],
            annee_publication=file_meta.get("annee_publication"),
        )
        for fact in facts:
            insert_fact(doc_id=doc_id, **fact)
        typer.echo(f"  → {len(facts)} fait(s) extrait(s) et insérés dans `facts`.")

    typer.echo("Ingestion terminée.")


@app.command()
def query(question: str = typer.Argument(..., help="Question en langage naturel")) -> None:
    """Interroge le RAG et affiche la réponse annotée."""
    from src.generation.answer import answer

    result = answer(question)
    typer.echo(f"\n[Type de requête : {result['query_type']}]\n")
    typer.echo(result["answer"])


@app.command()
def eval() -> None:
    """Lance l'évaluation sur le golden dataset via Langfuse."""
    from eval.run_eval import run_evaluation

    typer.echo("Lancement de l'évaluation …")
    run_evaluation()
    typer.echo("Évaluation terminée. Résultats dans Langfuse.")


if __name__ == "__main__":
    app()
