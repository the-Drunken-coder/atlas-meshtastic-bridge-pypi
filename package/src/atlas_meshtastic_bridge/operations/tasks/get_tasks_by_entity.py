from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Get tasks related to a specific entity."""
    entity_id = data.get("entity_id")
    if not entity_id:
        raise ValueError("get_tasks_by_entity requires 'entity_id'")
    return await client.get_tasks_by_entity(
        entity_id=str(entity_id), limit=int(data.get("limit", 25))
    )
