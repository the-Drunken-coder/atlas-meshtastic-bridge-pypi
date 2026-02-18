from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient
from atlas_meshtastic_bridge.operations.components import coerce_entity_components


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Update an existing entity's subtype or components."""
    entity_id = data.get("entity_id")
    if not entity_id:
        raise ValueError("update_entity requires 'entity_id'")
    payload: Dict[str, Any] = {}
    if "subtype" in data:
        payload["subtype"] = data.get("subtype")
    if "components" in data:
        payload["components"] = coerce_entity_components(data.get("components"))
    if not payload:
        raise ValueError("update_entity requires at least one of: subtype, components")
    return await client.update_entity(
        entity_id=str(entity_id),
        components=payload.get("components"),
        subtype=payload.get("subtype"),
    )
