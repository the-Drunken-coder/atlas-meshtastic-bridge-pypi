from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """List tasks (limit/offset only; server does not filter by status)."""
    if data.get("status") not in (None, ""):
        raise ValueError("list_tasks no longer supports 'status'; use limit/offset only")
    try:
        limit = int(data.get("limit", 25))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"list_tasks requires numeric 'limit'; got {data.get('limit')!r}") from exc
    try:
        offset = int(data.get("offset", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"list_tasks requires numeric 'offset'; got {data.get('offset')!r}"
        ) from exc
    payload: Dict[str, Any] = {
        "limit": limit,
        "offset": offset,
    }
    return await client.list_tasks(**payload)
