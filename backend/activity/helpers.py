from typing import Any

from backend.activity.service import store_activity_event


def emit_activity_event(**kwargs: Any) -> dict[str, Any] | None:
    """Best-effort helper for instrumentation calls across routes/agents/tasks."""
    try:
        return store_activity_event(kwargs)
    except Exception:
        return None
