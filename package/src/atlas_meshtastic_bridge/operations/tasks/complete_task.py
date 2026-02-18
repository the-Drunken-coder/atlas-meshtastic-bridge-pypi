from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Complete the task with optional result data."""
    task_id = data.get("task_id")
    if not task_id:
        raise ValueError("complete_task requires 'task_id'")
    result = data.get("result")
    return await client.complete_task(task_id=str(task_id), result=result)
