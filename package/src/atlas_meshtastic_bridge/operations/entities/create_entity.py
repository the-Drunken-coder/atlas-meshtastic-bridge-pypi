from __future__ import annotations

from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient
from atlas_meshtastic_bridge.operations.components import coerce_entity_components


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """Create a new entity with required identifiers."""
    entity_id = data.get("entity_id")
    entity_type = data.get("entity_type")
    alias = data.get("alias")
    subtype = data.get("subtype")
    if not entity_id or not entity_type or not alias or not subtype:
        raise ValueError(
            "create_entity requires 'entity_id', 'entity_type', 'alias', and 'subtype'"
        )
    return await client.create_entity(
        entity_id=str(entity_id),
        entity_type=str(entity_type),
        alias=str(alias),
        subtype=str(subtype),
        components=coerce_entity_components(data.get("components")),
    )
