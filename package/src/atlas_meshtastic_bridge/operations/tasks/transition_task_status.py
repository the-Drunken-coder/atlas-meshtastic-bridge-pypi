from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Transition a task to a new status."""
    task_id = data.get("task_id")
    status = data.get("status")
    if not task_id or not status:
        raise ValueError("transition_task_status requires 'task_id' and 'status'")
    return await client.transition_task_status(task_id=str(task_id), status=status)
