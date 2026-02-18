from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Delete a task by ID."""
    task_id = data.get("task_id")
    if not task_id:
        raise ValueError("delete_task requires 'task_id'")
    await client.delete_task(str(task_id))
    return {"deleted": str(task_id)}
