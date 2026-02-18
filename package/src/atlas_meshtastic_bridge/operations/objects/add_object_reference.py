from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Add a reference to an object."""
    object_id = data.get("object_id")
    if not object_id:
        raise ValueError("add_object_reference requires 'object_id'")
    if not data.get("entity_id") and not data.get("task_id"):
        raise ValueError("add_object_reference requires 'entity_id' or 'task_id'")
    return await client.add_object_reference(
        str(object_id),
        entity_id=data.get("entity_id"),
        task_id=data.get("task_id"),
    )
