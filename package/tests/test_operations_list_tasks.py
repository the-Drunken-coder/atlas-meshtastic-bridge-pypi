import asyncio
from unittest.mock import AsyncMock, MagicMock

from atlas_meshtastic_bridge.operations.tasks import list_tasks


def test_list_tasks_operation_rejects_deprecated_status() -> None:
    client = MagicMock()
    client.list_tasks = AsyncMock(return_value={"tasks": []})

    try:
        asyncio.run(
            list_tasks.run(
                client,
                envelope=None,
                data={"limit": 10, "offset": 3, "status": "PENDING"},
            )
        )
    except ValueError as exc:
        assert "no longer supports 'status'" in str(exc)
    else:
        raise AssertionError("expected status input to be rejected")

    client.list_tasks.assert_not_awaited()


def test_list_tasks_operation_defaults_offset_to_zero() -> None:
    client = MagicMock()
    client.list_tasks = AsyncMock(return_value={"tasks": []})

    asyncio.run(list_tasks.run(client, envelope=None, data={}))

    client.list_tasks.assert_awaited_once_with(limit=25, offset=0)
