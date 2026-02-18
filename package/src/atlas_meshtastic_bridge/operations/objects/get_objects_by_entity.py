from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """List objects attached to an entity."""
    entity_id = data.get("entity_id")
    if not entity_id:
        raise ValueError("get_objects_by_entity requires 'entity_id'")
    payload = {"entity_id": entity_id, "limit": int(data.get("limit", 50))}
    return await client.get_objects_by_entity(**payload)
