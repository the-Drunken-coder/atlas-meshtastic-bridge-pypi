from __future__ import annotations

import base64
import io
from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Create an object with inline base64 content."""
    object_id = data.get("object_id")
    content_b64 = data.get("content_b64")
    usage_hint = data.get("usage_hint")
    content_type = data.get("content_type")
    object_type = data.get("type")
    file_name = data.get("file_name") or f"{object_id}.bin"
    referenced_by = data.get("referenced_by")
    if not object_id or not content_b64 or not content_type:
        raise ValueError("create_object requires 'object_id', 'content_b64', and 'content_type'")
    try:
        raw = base64.b64decode(content_b64)
    except Exception as exc:
        raise ValueError("content_b64 must be valid base64") from exc
    buffer = io.BytesIO(raw)
    buffer.name = file_name
    return await client.create_object(
        file=buffer,
        object_id=str(object_id),
        usage_hint=usage_hint,
        content_type=content_type,
        object_type=object_type,
        referenced_by=referenced_by,
    )
