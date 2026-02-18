from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Find orphaned objects with paging support."""
    limit = int(data.get("limit", 100))
    offset = int(data.get("offset", 0))
    return await client.find_orphaned_objects(limit=limit, offset=offset)
