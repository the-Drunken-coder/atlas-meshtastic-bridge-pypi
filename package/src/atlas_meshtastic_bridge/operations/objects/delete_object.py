from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Delete an object by ID."""
    object_id = data.get("object_id")
    if not object_id:
        raise ValueError("delete_object requires 'object_id'")
    await client.delete_object(str(object_id))
    return {"deleted": str(object_id)}
