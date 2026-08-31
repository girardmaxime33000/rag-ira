from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ollama_host: str = "http://localhost:11434"
    ollama_llm_model: str = "qwen3:4b"
    ollama_embed_model: str = "bge-m3"
    embed_dim: int = 1024

    rag_db_dsn: str = "postgresql://rag:rag@localhost:5432/rag"

    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    # Serveur HTTP compatible OpenAI (pour brancher Open WebUI) — 100% local,
    # ne fait que mimer le format de câblage OpenAI, aucun appel externe.
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: str = "rag-ira-local"


settings = Settings()
