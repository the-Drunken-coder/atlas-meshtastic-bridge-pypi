from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Get a single entity ensuring an ID is provided."""
    entity_id = data.get("entity_id") or data.get("id")
    if not entity_id:
        raise ValueError("get_entity requires 'entity_id'")
    return await client.get_entity(entity_id=str(entity_id))
