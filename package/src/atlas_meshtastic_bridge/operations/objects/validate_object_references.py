from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Validate references for an object."""
    object_id = data.get("object_id")
    if not object_id:
        raise ValueError("validate_object_references requires 'object_id'")
    return await client.validate_object_references(str(object_id))
