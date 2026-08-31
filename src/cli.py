from pathlib import Path

import typer

app = typer.Typer(help="RAG local — statistiques de la profession artistique en France")


@app.command()
def ingest(path: Path = typer.Argument(..., help="Chemin vers un fichier PDF à ingérer")) -> None:
    """Ingère un document PDF : parse, route, embed et stocke."""
    if not path.exists():
        typer.echo(f"Fichier introuvable : {path}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Conversion de {path} …")
    _ingest_one(path)
    typer.echo("Ingestion terminée.")


@app.command(name="ingest-all")
def ingest_all(
    folder: Path = typer.Argument(Path("data/raw"), help="Dossier contenant les PDFs à ingérer"),
) -> None:
    """Ingère tous les PDFs d'un dossier séquentiellement (économise la mémoire)."""
    pdfs = sorted(folder.glob("**/*.pdf"))
    if not pdfs:
        typer.echo(f"Aucun PDF trouvé dans {folder}", err=True)
        raise typer.Exit(1)

    typer.echo(f"{len(pdfs)} PDF(s) trouvé(s) dans {folder}")
    failed: list[tuple[Path, str]] = []

    for i, pdf in enumerate(pdfs, 1):
        typer.echo(f"\n[{i}/{len(pdfs)}] {pdf.name}")
        try:
            _ingest_one(pdf)
        except Exception as exc:
            typer.echo(f"  ✗ Erreur : {exc}", err=True)
            failed.append((pdf, str(exc)))

    typer.echo(f"\n{'─'*60}")
    typer.echo(f"Terminé : {len(pdfs) - len(failed)}/{len(pdfs)} ingérés avec succès.")
    if failed:
        typer.echo(f"{len(failed)} échec(s) :")
        for path, err in failed:
            typer.echo(f"  ✗ {path.name} — {err}")


def _ingest_one(path: Path) -> None:
    """Core ingestion logic shared between `ingest` and `ingest-all`."""
    from src.ingestion.convert import convert_document
    from src.ingestion.route import route_document
    from src.ingestion.metadata import extract_from_filename, extract_with_llm
    from src.ingestion.load import upsert_document, insert_chunk, insert_fact, sha256_file
    from src.ingestion.table_parser import parse_tables
    from src.embeddings.embedder import embed

    typer.echo(f"  Conversion …")
    doc = convert_document(path)
    routed = route_document(doc)

    file_meta = extract_from_filename(path)
    llm_meta: dict = {}
    if routed.narrative_chunks:
        typer.echo("  Extraction des métadonnées via LLM …")
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

    typer.echo(f"  Embedding de {len(routed.narrative_chunks)} chunks …")
    for text in routed.narrative_chunks:
        vector = embed(text)
        insert_chunk(doc_id=doc_id, text=text, embedding=vector, metadata=llm_meta)

    if routed.raw_tables:
        typer.echo(f"  Extraction de {len(routed.raw_tables)} tableau(x) → facts …")
        facts = parse_tables(
            routed.raw_tables,
            source=file_meta["source"],
            annee_publication=file_meta.get("annee_publication"),
            doc=routed.doc,
        )
        for fact in facts:
            insert_fact(doc_id=doc_id, **fact)
        typer.echo(f"  → {len(facts)} fait(s) insérés dans `facts`.")


@app.command()
def query(question: str = typer.Argument(..., help="Question en langage naturel")) -> None:
    """Interroge le RAG et affiche la réponse annotée."""
    from src.generation.answer import answer

    result = answer(question)
    typer.echo(f"\n[Type de requête : {result['query_type']}]\n")
    typer.echo(result["answer"])


@app.command()
def serve() -> None:
    """Démarre le serveur HTTP compatible OpenAI (pour Open WebUI)."""
    import uvicorn

    from config.settings import settings

    url = f"http://{settings.api_host}:{settings.api_port}/v1"
    typer.echo(f"Serveur compatible OpenAI sur {url}")
    uvicorn.run(
        "src.api.openai_compat:app", host=settings.api_host, port=settings.api_port
    )


@app.command()
def eval() -> None:
    """Lance l'évaluation sur le golden dataset via Langfuse."""
    from eval.run_eval import run_evaluation

    typer.echo("Lancement de l'évaluation …")
    run_evaluation()
    typer.echo("Évaluation terminée. Résultats dans Langfuse.")


if __name__ == "__main__":
    app()
