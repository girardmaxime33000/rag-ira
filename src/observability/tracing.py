import functools
from typing import Any, Callable, TypeVar
from langfuse import Langfuse
from config.settings import settings

F = TypeVar("F", bound=Callable[..., Any])

_client: Langfuse | None = None


def get_client() -> Langfuse:
    global _client
    if _client is None:
        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    return _client


def observe(name: str | None = None) -> Callable[[F], F]:
    """Decorator that wraps a function in a Langfuse span."""
    def decorator(fn: F) -> F:
        span_name = name or fn.__name__

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            client = get_client()
            trace = client.trace(name=span_name)
            span = trace.span(name=span_name)
            try:
                result = fn(*args, **kwargs)
                span.end(output=str(result)[:500] if result is not None else None)
                return result
            except Exception as exc:
                span.end(level="ERROR", status_message=str(exc))
                raise

        return wrapper  # type: ignore[return-value]

    return decorator
