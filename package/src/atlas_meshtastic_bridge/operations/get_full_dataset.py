from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Fetch a full dataset with optional limits."""
    payload: Dict[str, Any] = {}
    for key in ("entity_limit", "task_limit", "object_limit"):
        if key in data and data.get(key) is not None:
            payload[key] = data.get(key)
    return await client.get_full_dataset(**payload)
