from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """List objects with limit/offset defaults."""
    limit = int(data.get("limit", 20))
    offset = int(data.get("offset", 0))
    content_type = data.get("content_type")
    return await client.list_objects(
        limit=limit,
        offset=offset,
        content_type=content_type,
    )
