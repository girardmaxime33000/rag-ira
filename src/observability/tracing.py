import functools
import os
from typing import Any, Callable, TypeVar

from config.settings import settings

os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)

F = TypeVar("F", bound=Callable[..., Any])

_observe_impl: Callable | None = None


def _get_observe():
    global _observe_impl
    if _observe_impl is not None:
        return _observe_impl

    # Langfuse v2+
    try:
        from langfuse.decorators import observe as lf_observe
        _observe_impl = lf_observe
        return _observe_impl
    except ImportError:
        pass

    # Langfuse v1 — no decorator API, build a manual span wrapper
    try:
        from langfuse import Langfuse
        _lf = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )

        def _v1_observe(name: str | None = None):
            def decorator(fn: F) -> F:
                span_name = name or fn.__name__
                @functools.wraps(fn)
                def wrapper(*args: Any, **kwargs: Any) -> Any:
                    try:
                        trace = _lf.trace(name=span_name)
                        span = trace.span(name=span_name)
                        result = fn(*args, **kwargs)
                        span.end()
                        return result
                    except Exception:
                        return fn(*args, **kwargs)
                return wrapper  # type: ignore[return-value]
            return decorator

        _observe_impl = _v1_observe
        return _observe_impl
    except Exception:
        pass

    # Fallback : no-op
    def _noop(name: str | None = None):
        def decorator(fn: F) -> F:
            return fn
        return decorator

    _observe_impl = _noop
    return _observe_impl


def observe(name: str | None = None):
    return _get_observe()(name=name)
