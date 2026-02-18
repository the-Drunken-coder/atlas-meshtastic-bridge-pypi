from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Check in an entity and optionally return pending tasks."""
    entity_id = data.get("entity_id")
    if not entity_id:
        raise ValueError("checkin_entity requires 'entity_id'")
    payload = {"entity_id": entity_id}
    for key in ("latitude", "longitude", "altitude_m", "speed_m_s", "heading_deg"):
        if key in data:
            payload[key] = data[key]
    if "status_filter" in data:
        payload["status_filter"] = data["status_filter"]
    if "limit" in data:
        payload["limit"] = data["limit"]
    if "since" in data:
        payload["since"] = data["since"]
    if "fields" in data:
        payload["fields"] = data["fields"]
    return await client.checkin_entity(**payload)
