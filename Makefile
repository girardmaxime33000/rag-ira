.PHONY: setup up down langfuse-up langfuse-down webui-up webui-down api ingest ingest-all query eval test lint

OLLAMA_MODELS := qwen3:4b bge-m3

setup:
	uv sync
	@echo "Pulling Ollama models: $(OLLAMA_MODELS)"
	@for model in $(OLLAMA_MODELS); do \
		echo "→ ollama pull $$model"; \
		ollama pull $$model; \
	done

up:
	docker compose up -d postgres

down:
	docker compose down

langfuse-up:
	docker compose -f third_party/langfuse/docker-compose.yml up -d

langfuse-down:
	docker compose -f third_party/langfuse/docker-compose.yml down

webui-up:
	docker compose -f third_party/open-webui/docker-compose.yml up -d
	@echo "Open WebUI disponible sur http://localhost:3001 (lance 'make api' côté hôte)"

webui-down:
	docker compose -f third_party/open-webui/docker-compose.yml down

api:
	uv run python -m src.cli serve

# OBJC_DISABLE_INITIALIZE_FORK_SAFETY évite un crash natif (SIGTRAP) sur macOS
# quand RapidOCR/onnxruntime fork() après init d'un thread Objective-C. No-op ailleurs.
ingest:
	@test -n "$(FILE)" || (echo "Usage: make ingest FILE=path/to/document.pdf" && exit 1)
	OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES uv run python -m src.cli ingest "$(FILE)"

ingest-all:
	@echo "Ingestion séquentielle de tous les PDFs dans data/raw/ …"
	OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES uv run python -m src.cli ingest-all data/raw/

query:
	@test -n "$(Q)" || (echo "Usage: make query Q='votre question'" && exit 1)
	uv run python -m src.cli query "$(Q)"

eval:
	uv run python -m src.cli eval

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check src/ tests/ eval/ config/
	uv run mypy src/ config/ --ignore-missing-imports
