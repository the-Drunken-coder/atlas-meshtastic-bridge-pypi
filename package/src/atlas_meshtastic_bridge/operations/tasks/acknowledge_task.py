from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Acknowledge a task, ensuring we operate on the requested ID."""
    task_id = data.get("task_id")
    if not task_id:
        raise ValueError("acknowledge_task requires 'task_id'")
    return await client.acknowledge_task(task_id=str(task_id))
