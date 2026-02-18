from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Update telemetry for an entity, ensuring location info is provided."""
    entity_id = data.get("entity_id")
    if not entity_id:
        raise ValueError("update_entity_telemetry requires 'entity_id'")
    payload = {"entity_id": entity_id}
    for key in ("latitude", "longitude", "altitude_m", "speed_m_s", "heading_deg"):
        if key in data:
            payload[key] = data[key]
    if len(payload) == 1:
        raise ValueError("update_entity_telemetry requires at least one telemetry field")
    return await client.update_entity_telemetry(**payload)
