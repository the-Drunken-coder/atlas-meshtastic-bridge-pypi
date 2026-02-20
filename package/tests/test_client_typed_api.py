from datetime import datetime
from unittest.mock import MagicMock

import pytest
from atlas_asset_http_client_python.components import EntityComponents
from atlas_meshtastic_bridge.client import MeshtasticClient


def _client_with_mock() -> MeshtasticClient:
    client = MeshtasticClient(transport=MagicMock(), gateway_node_id="gw")
    client.send_request = MagicMock(return_value="ok")  # type: ignore[assignment]
    return client


def test_checkin_entity_wrapper_builds_payload() -> None:
    client = _client_with_mock()
    resp = client.checkin_entity(
        "asset-1",
        latitude=1.0,
        altitude_m=2.5,
        limit=7,
        status_filter="pending",
        fields="minimal",
    )

    assert resp == "ok"
    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="checkin_entity",
        data={
            "entity_id": "asset-1",
            "status_filter": "pending",
            "limit": 7,
            "fields": "minimal",
            "latitude": 1.0,
            "altitude_m": 2.5,
        },
    )


def test_update_telemetry_requires_fields() -> None:
    client = _client_with_mock()
    with pytest.raises(ValueError):
        client.update_telemetry("asset-1")


def test_get_changed_since_converts_datetime() -> None:
    client = _client_with_mock()
    now = datetime(2026, 1, 5, 12, 0, 0)

    client.get_changed_since(now, limit_per_type=5)

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="get_changed_since",
        data={"since": now.isoformat(), "limit_per_type": 5},
    )


def test_create_entity_requires_fields() -> None:
    client = _client_with_mock()
    with pytest.raises(ValueError):
        client.create_entity("", "type", "alias", "sub")
    resp = client.create_entity(
        "e1",
        "asset",
        "alias",
        "drone",
        components=EntityComponents(custom_status="ok"),
    )
    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="create_entity",
        data={
            "entity_id": "e1",
            "entity_type": "asset",
            "alias": "alias",
            "subtype": "drone",
            "components": {"custom_status": "ok"},
        },
    )
    assert resp == "ok"


def test_create_entity_rejects_raw_dict_components() -> None:
    client = _client_with_mock()
    with pytest.raises(TypeError, match="Expected EntityComponents or TaskComponents"):
        client.create_entity(  # type: ignore[arg-type]
            "e1",
            "asset",
            "alias",
            "drone",
            components={"custom_status": "ok"},  # type: ignore[arg-type]
        )


def test_transition_task_status_requires_fields() -> None:
    client = _client_with_mock()
    with pytest.raises(ValueError):
        client.transition_task_status("", "")
    resp = client.transition_task_status("t1", "completed")
    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="transition_task_status",
        data={"task_id": "t1", "status": "completed"},
    )
    assert resp == "ok"


def test_add_object_reference_requires_target() -> None:
    client = _client_with_mock()
    with pytest.raises(ValueError):
        client.add_object_reference("obj-1")
    client.send_request.reset_mock()  # type: ignore[attr-defined]
    resp = client.add_object_reference("obj-1", entity_id="e1")
    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="add_object_reference",
        data={"object_id": "obj-1", "entity_id": "e1"},
    )
    assert resp == "ok"


def test_test_echo_builds_payload() -> None:
    client = _client_with_mock()
    client.test_echo("hello")

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="test_echo",
        data={"message": "hello"},
    )


def test_test_echo_default_message() -> None:
    client = _client_with_mock()
    client.test_echo()

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="test_echo",
        data={"message": "ping"},
    )


def test_list_entities_builds_payload() -> None:
    client = _client_with_mock()
    client.list_entities(limit=10, offset=5)

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="list_entities",
        data={"limit": 10, "offset": 5},
    )


def test_list_entities_default_params() -> None:
    client = _client_with_mock()
    client.list_entities()

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="list_entities",
        data={"limit": 5, "offset": 0},
    )


def test_get_entity_builds_payload() -> None:
    client = _client_with_mock()
    client.get_entity("entity-123")

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="get_entity",
        data={"entity_id": "entity-123"},
    )


def test_get_entity_requires_entity_id() -> None:
    client = _client_with_mock()
    with pytest.raises(ValueError, match="get_entity requires 'entity_id'"):
        client.get_entity("")


def test_get_entity_by_alias_builds_payload() -> None:
    client = _client_with_mock()
    client.get_entity_by_alias("my-alias")

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="get_entity_by_alias",
        data={"alias": "my-alias"},
    )


def test_get_entity_by_alias_requires_alias() -> None:
    client = _client_with_mock()
    with pytest.raises(ValueError, match="get_entity_by_alias requires 'alias'"):
        client.get_entity_by_alias("")


def test_update_telemetry_builds_payload() -> None:
    client = _client_with_mock()
    client.update_telemetry("entity-1", latitude=1.0, longitude=2.0, altitude_m=100.0)

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="update_telemetry",
        data={
            "entity_id": "entity-1",
            "latitude": 1.0,
            "longitude": 2.0,
            "altitude_m": 100.0,
        },
    )


def test_update_telemetry_requires_entity_id() -> None:
    client = _client_with_mock()
    with pytest.raises(ValueError, match="update_telemetry requires 'entity_id'"):
        client.update_telemetry("", latitude=1.0)


def test_list_tasks_builds_payload() -> None:
    client = _client_with_mock()
    client.list_tasks(status="pending", limit=50, offset=4)

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="list_tasks",
        data={"status": "pending", "limit": 50, "offset": 4},
    )


def test_list_tasks_default_params() -> None:
    client = _client_with_mock()
    client.list_tasks()

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="list_tasks",
        data={"limit": 25, "offset": 0},
    )


def test_get_task_builds_payload() -> None:
    client = _client_with_mock()
    client.get_task("task-123")

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="get_task",
        data={"task_id": "task-123"},
    )


def test_get_task_requires_task_id() -> None:
    client = _client_with_mock()
    with pytest.raises(ValueError, match="get_task requires 'task_id'"):
        client.get_task("")


def test_get_tasks_by_entity_builds_payload() -> None:
    client = _client_with_mock()
    client.get_tasks_by_entity("entity-1", limit=10)

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="get_tasks_by_entity",
        data={"entity_id": "entity-1", "limit": 10},
    )


def test_get_tasks_by_entity_requires_entity_id() -> None:
    client = _client_with_mock()
    with pytest.raises(ValueError, match="get_tasks_by_entity requires 'entity_id'"):
        client.get_tasks_by_entity("")


def test_start_task_builds_payload() -> None:
    client = _client_with_mock()
    client.start_task("task-123")

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="start_task",
        data={"task_id": "task-123"},
    )


def test_start_task_requires_task_id() -> None:
    client = _client_with_mock()
    with pytest.raises(ValueError, match="start_task requires 'task_id'"):
        client.start_task("")


def test_complete_task_builds_payload() -> None:
    client = _client_with_mock()
    client.complete_task("task-123", result={"status": "success"})

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="complete_task",
        data={"task_id": "task-123", "result": {"status": "success"}},
    )


def test_complete_task_without_result() -> None:
    client = _client_with_mock()
    client.complete_task("task-123")

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="complete_task",
        data={"task_id": "task-123"},
    )


def test_complete_task_requires_task_id() -> None:
    client = _client_with_mock()
    with pytest.raises(ValueError, match="complete_task requires 'task_id'"):
        client.complete_task("")


def test_fail_task_builds_payload() -> None:
    client = _client_with_mock()
    client.fail_task("task-123", error_message="Failed", error_details={"code": 500})

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="fail_task",
        data={
            "task_id": "task-123",
            "error_message": "Failed",
            "error_details": {"code": 500},
        },
    )


def test_fail_task_without_error_details() -> None:
    client = _client_with_mock()
    client.fail_task("task-123")

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="fail_task",
        data={"task_id": "task-123"},
    )


def test_fail_task_requires_task_id() -> None:
    client = _client_with_mock()
    with pytest.raises(ValueError, match="fail_task requires 'task_id'"):
        client.fail_task("")


def test_list_objects_builds_payload() -> None:
    client = _client_with_mock()
    client.list_objects(limit=30, offset=10, content_type="image/jpeg")

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="list_objects",
        data={"limit": 30, "offset": 10, "content_type": "image/jpeg"},
    )


def test_list_objects_default_params() -> None:
    client = _client_with_mock()
    client.list_objects()

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="list_objects",
        data={"limit": 20, "offset": 0},
    )


def test_get_object_builds_payload() -> None:
    client = _client_with_mock()
    client.get_object("object-123", download=True)

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="get_object",
        data={"object_id": "object-123", "download": True},
    )


def test_get_object_without_download() -> None:
    client = _client_with_mock()
    client.get_object("object-123")

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="get_object",
        data={"object_id": "object-123"},
    )


def test_get_object_requires_object_id() -> None:
    client = _client_with_mock()
    with pytest.raises(ValueError, match="get_object requires 'object_id'"):
        client.get_object("")


def test_get_objects_by_entity_builds_payload() -> None:
    client = _client_with_mock()
    client.get_objects_by_entity("entity-1", limit=100)

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="get_objects_by_entity",
        data={"entity_id": "entity-1", "limit": 100},
    )


def test_get_objects_by_entity_requires_entity_id() -> None:
    client = _client_with_mock()
    with pytest.raises(ValueError, match="get_objects_by_entity requires 'entity_id'"):
        client.get_objects_by_entity("")


def test_get_objects_by_task_builds_payload() -> None:
    client = _client_with_mock()
    client.get_objects_by_task("task-123", limit=75)

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="get_objects_by_task",
        data={"task_id": "task-123", "limit": 75},
    )


def test_get_objects_by_task_requires_task_id() -> None:
    client = _client_with_mock()
    with pytest.raises(ValueError, match="get_objects_by_task requires 'task_id'"):
        client.get_objects_by_task("")


def test_checkin_entity_requires_entity_id() -> None:
    client = _client_with_mock()
    with pytest.raises(ValueError, match="checkin_entity requires 'entity_id'"):
        client.checkin_entity("")


def test_checkin_entity_with_datetime_since() -> None:
    client = _client_with_mock()
    since_dt = datetime(2026, 1, 5, 10, 30, 0)
    client.checkin_entity("entity-1", since=since_dt, fields="minimal")

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="checkin_entity",
        data={
            "entity_id": "entity-1",
            "status_filter": "pending,in_progress",
            "limit": 10,
            "since": since_dt.isoformat(),
            "fields": "minimal",
        },
    )


def test_get_changed_since_with_string() -> None:
    client = _client_with_mock()
    client.get_changed_since("2026-01-05T12:00:00")

    client.send_request.assert_called_once_with(  # type: ignore[attr-defined]
        command="get_changed_since",
        data={"since": "2026-01-05T12:00:00"},
    )
