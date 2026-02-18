from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from atlas_asset_http_client_python import AtlasCommandHttpClient


@dataclass
class ListEntitiesContext:
    limit: int
    offset: int


def _build_context(data: Dict[str, Any]) -> ListEntitiesContext:
    return ListEntitiesContext(
        limit=int(data.get("limit", 10)),
        offset=int(data.get("offset", 0)),
    )


async def run(
    client: AtlasCommandHttpClient,
    envelope: Any,
    data: Dict[str, Any],
) -> Any:
    """List entities with sanitized pagination arguments."""
    context = _build_context(data)
    return await client.list_entities(limit=context.limit, offset=context.offset)
