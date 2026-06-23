import ollama

from config.settings import settings


def embed(text: str) -> list[float]:
    response = ollama.embeddings(model=settings.ollama_embed_model, prompt=text)
    vector: list[float] = response["embedding"]
    if len(vector) != settings.embed_dim:
        raise ValueError(
            f"Expected embedding dim {settings.embed_dim}, got {len(vector)}. "
            f"Check OLLAMA_EMBED_MODEL={settings.ollama_embed_model}."
        )
    return vector


def embed_batch(texts: list[str]) -> list[list[float]]:
    return [embed(t) for t in texts]
