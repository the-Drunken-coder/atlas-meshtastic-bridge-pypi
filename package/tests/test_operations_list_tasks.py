import asyncio
from unittest.mock import AsyncMock, MagicMock

from atlas_meshtastic_bridge.operations.tasks import list_tasks


def test_list_tasks_operation_forwards_offset_and_status() -> None:
    client = MagicMock()
    client.list_tasks = AsyncMock(return_value={"tasks": []})

    result = asyncio.run(
        list_tasks.run(
            client,
            envelope=None,
            data={"limit": 10, "offset": 3, "status": "PENDING"},
        )
    )

    client.list_tasks.assert_awaited_once_with(limit=10, offset=3, status="pending")
    assert result == {"tasks": []}


def test_list_tasks_operation_defaults_offset_to_zero() -> None:
    client = MagicMock()
    client.list_tasks = AsyncMock(return_value={"tasks": []})

    asyncio.run(list_tasks.run(client, envelope=None, data={}))

    client.list_tasks.assert_awaited_once_with(limit=25, offset=0)
