from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Get a single task by ID."""
    task_id = data.get("task_id")
    if not task_id:
        raise ValueError("get_task requires 'task_id'")
    return await client.get_task(task_id=str(task_id))
