from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Get an object by ID, optionally download raw bytes."""
    object_id = data.get("object_id")
    if not object_id:
        raise ValueError("get_object requires 'object_id'")
    if data.get("download"):
        content, content_type, length = await client.download_object(object_id=str(object_id))
        return {
            "object_id": object_id,
            "content_type": content_type,
            "size": length,
            "content": content,
        }
    return await client.get_object(object_id=str(object_id))
