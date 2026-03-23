from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """List objects with limit/offset defaults."""
    if data.get("content_type") not in (None, ""):
        raise ValueError(
            "list_objects no longer supports 'content_type' filtering; use limit/offset only"
        )
    limit = int(data.get("limit", 20))
    offset = int(data.get("offset", 0))
    return await client.list_objects(
        limit=limit,
        offset=offset,
    )
