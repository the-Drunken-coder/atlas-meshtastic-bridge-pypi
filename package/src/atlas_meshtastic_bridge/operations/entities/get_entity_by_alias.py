from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Get an entity by alias."""
    alias = data.get("alias")
    if not alias:
        raise ValueError("get_entity_by_alias requires 'alias'")
    return await client.get_entity_by_alias(alias=str(alias))
