from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient

VALID_STATUSES = {"pending", "acknowledged", "completed", "cancelled"}


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """List tasks with optional status filtering."""
    payload: Dict[str, Any] = {
        "limit": int(data.get("limit", 25)),
        "offset": int(data.get("offset", 0)),
    }
    status = data.get("status")
    if status:
        normalized = status if status in VALID_STATUSES else status.lower()
        payload["status"] = normalized
    return await client.list_tasks(**payload)
