from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Delete an entity by ID."""
    entity_id = data.get("entity_id")
    if not entity_id:
        raise ValueError("delete_entity requires 'entity_id'")
    await client.delete_entity(str(entity_id))
    return {"deleted": str(entity_id)}
