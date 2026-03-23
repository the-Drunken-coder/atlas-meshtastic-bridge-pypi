from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Mark a task as failed with optional details."""
    task_id = data.get("task_id")
    if not task_id:
        raise ValueError("fail_task requires 'task_id'")
    kwargs: Dict[str, Any] = {}
    if "error_message" in data:
        kwargs["error_message"] = data["error_message"]
    if "error_details" in data:
        kwargs["error_details"] = data["error_details"]
    if "error" in data and isinstance(data["error"], dict):
        err = data["error"]
        if "message" in err:
            kwargs["error_message"] = err["message"]
        if "details" in err:
            kwargs["error_details"] = err["details"]
    return await client.fail_task(task_id=str(task_id), **kwargs)
