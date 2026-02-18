from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Retrieve changes since the provided timestamp."""
    since = data.get("since")
    if not since:
        raise ValueError("get_changed_since requires 'since'")
    if isinstance(since, str):
        since_value = since
    elif isinstance(since, datetime):
        since_value = since.isoformat()
    else:
        raise ValueError("Parameter 'since' must be datetime or ISO string")
    return await client.get_changed_since(
        since=since_value, limit_per_type=data.get("limit_per_type")
    )
