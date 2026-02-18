from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Update object metadata."""
    object_id = data.get("object_id")
    if not object_id:
        raise ValueError("update_object requires 'object_id'")
    payload: Dict[str, Any] = {}
    if "usage_hints" in data:
        payload["usage_hints"] = data.get("usage_hints")
    if "referenced_by" in data:
        payload["referenced_by"] = data.get("referenced_by")
    if not payload:
        raise ValueError("update_object requires at least one of: usage_hints, referenced_by")
    return await client.update_object(str(object_id), **payload)
