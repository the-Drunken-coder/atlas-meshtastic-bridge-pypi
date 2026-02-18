from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """List objects attached to a task."""
    task_id = data.get("task_id")
    if not task_id:
        raise ValueError("get_objects_by_task requires 'task_id'")
    payload = {"task_id": task_id, "limit": int(data.get("limit", 50))}
    return await client.get_objects_by_task(**payload)
