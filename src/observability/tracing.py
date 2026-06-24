from langfuse.decorators import observe as _langfuse_observe, langfuse_context
from config.settings import settings
import os

# Inject credentials so the decorator picks them up from env
os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)


def observe(name: str | None = None):
    """Wrapper around langfuse_context observe decorator."""
    return _langfuse_observe(name=name)
