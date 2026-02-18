from __future__ import annotations

from typing import Any, Dict


async def run(
    client: Any,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Echo back whatever was passed so we can verify chunk handling."""
    return {"echo": data, "id": getattr(envelope, "id", None)}
