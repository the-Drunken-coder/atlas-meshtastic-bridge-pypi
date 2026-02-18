from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient
from atlas_meshtastic_bridge.operations.components import coerce_task_components


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Create a new task."""
    task_id = data.get("task_id")
    if not task_id:
        raise ValueError("create_task requires 'task_id'")
    payload: Dict[str, Any] = {"task_id": str(task_id)}
    if "status" in data:
        payload["status"] = data.get("status")
    if "entity_id" in data:
        payload["entity_id"] = data.get("entity_id")
    if "components" in data:
        payload["components"] = coerce_task_components(data.get("components"))
    if "extra" in data:
        payload["extra"] = data.get("extra")
    return await client.create_task(**payload)
