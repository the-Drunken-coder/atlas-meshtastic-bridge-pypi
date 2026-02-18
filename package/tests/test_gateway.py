"""Unit tests for MeshtasticGateway."""

from unittest.mock import MagicMock, patch

import pytest
from atlas_meshtastic_bridge.gateway import DEFAULT_COMMAND_MAP, MeshtasticGateway
from atlas_meshtastic_bridge.message import MessageEnvelope
from atlas_meshtastic_bridge.transport import (
    InMemoryRadio,
    InMemoryRadioBus,
    MeshtasticTransport,
)


def test_gateway_initialization() -> None:
    """Test MeshtasticGateway initialization."""
    transport = MeshtasticTransport(InMemoryRadio("gateway"))
    gateway = MeshtasticGateway(
        transport=transport,
        api_base_url="http://localhost:8000",
        token="test-token",
        command_map={"custom": "custom.operation"},
    )

    assert gateway.transport == transport
    assert gateway.api_base_url == "http://localhost:8000"
    assert gateway.token == "test-token"
    assert gateway.command_map == {"custom": "custom.operation"}
    assert gateway._running is False


def test_gateway_initialization_default_command_map() -> None:
    """Test gateway uses default command map when none provided."""
    transport = MeshtasticTransport(InMemoryRadio("gateway"))
    gateway = MeshtasticGateway(
        transport=transport,
        api_base_url="http://localhost:8000",
    )

    assert gateway.command_map == DEFAULT_COMMAND_MAP


def test_gateway_run_once_no_message() -> None:
    """Test run_once when no message is received."""
    transport = MeshtasticTransport(InMemoryRadio("gateway"))
    gateway = MeshtasticGateway(
        transport=transport,
        api_base_url="http://localhost:8000",
    )

    # Should complete without error when no message
    gateway.run_once(timeout=0.1)
    # No assertion needed - just verifying it doesn't crash


def test_gateway_run_once_non_request_message() -> None:
    """Test run_once ignores non-request message types."""
    bus = InMemoryRadioBus()
    sender_transport = MeshtasticTransport(InMemoryRadio("sender", bus))
    gateway_transport = MeshtasticTransport(InMemoryRadio("gateway", bus))

    gateway = MeshtasticGateway(
        transport=gateway_transport,
        api_base_url="http://localhost:8000",
    )

    # Send a response message (not a request)
    envelope = MessageEnvelope(
        id="non-request",
        type="response",
        command="test",
        data={},
    )
    sender_transport.send_message(envelope, "gateway")

    # Gateway should ignore it
    gateway.run_once(timeout=0.5)

    # No response should be sent back
    sender, response = sender_transport.receive_message(timeout=0.1)
    assert response is None


def test_gateway_run_once_duplicate_request() -> None:
    """Test run_once ignores duplicate requests."""
    bus = InMemoryRadioBus()
    sender_transport = MeshtasticTransport(InMemoryRadio("sender", bus))
    gateway_transport = MeshtasticTransport(InMemoryRadio("gateway", bus))

    gateway = MeshtasticGateway(
        transport=gateway_transport,
        api_base_url="http://localhost:8000",
    )

    envelope = MessageEnvelope(
        id="duplicate-test",
        type="request",
        command="test_echo",
        data={"msg": "hello"},
    )

    # Send same request twice
    sender_transport.send_message(envelope, "gateway")

    # Process first request
    with patch.object(gateway, "_handle_request") as mock_handle:
        mock_handle.return_value = MessageEnvelope(
            id=envelope.id,
            type="response",
            command=envelope.command,
            data={"result": "ok"},
        )
        gateway.run_once(timeout=0.5)
        assert mock_handle.call_count == 1

    # Send duplicate
    sender_transport.send_message(envelope, "gateway")

    # Process duplicate (should be ignored)
    with patch.object(gateway, "_handle_request") as mock_handle:
        gateway.run_once(timeout=0.5)
        assert mock_handle.call_count == 0  # Should not be called for duplicate


def test_gateway_handle_request_unknown_command() -> None:
    """Test _handle_request with unknown command returns error."""
    transport = MeshtasticTransport(InMemoryRadio("gateway"))
    gateway = MeshtasticGateway(
        transport=transport,
        api_base_url="http://localhost:8000",
    )

    envelope = MessageEnvelope(
        id="unknown-cmd",
        type="request",
        command="unknown_command",
        data={},
    )

    response = gateway._handle_request(envelope)

    assert response.id == envelope.id
    assert response.type == "error"
    assert response.command == "unknown_command"
    assert response.data is not None
    assert "Unknown command" in response.data["error"]


def test_gateway_handle_request_echo_operation() -> None:
    """Test _handle_request with test_echo operation."""
    transport = MeshtasticTransport(InMemoryRadio("gateway"))
    gateway = MeshtasticGateway(
        transport=transport,
        api_base_url="http://localhost:8000",
    )

    envelope = MessageEnvelope(
        id="echo-test",
        type="request",
        command="test_echo",
        data={"message": "hello world"},
    )

    response = gateway._handle_request(envelope)

    assert response.id == envelope.id
    assert response.type == "response"
    assert response.command == "test_echo"
    assert response.data is not None
    assert "result" in response.data
    assert response.data["result"]["echo"] == {"message": "hello world"}
    assert response.data["result"]["id"] == "echo-test"


def test_gateway_load_operation_success() -> None:
    """Test _load_operation successfully loads an operation module."""
    transport = MeshtasticTransport(InMemoryRadio("gateway"))
    gateway = MeshtasticGateway(
        transport=transport,
        api_base_url="http://localhost:8000",
    )

    # Load the echo operation
    module = gateway._load_operation("_echo")

    assert module is not None
    assert hasattr(module, "run")


def test_gateway_load_operation_not_found() -> None:
    """Test _load_operation raises error for non-existent operation."""
    transport = MeshtasticTransport(InMemoryRadio("gateway"))
    gateway = MeshtasticGateway(
        transport=transport,
        api_base_url="http://localhost:8000",
    )

    with pytest.raises(ValueError, match="not implemented"):
        gateway._load_operation("nonexistent_operation")


def test_gateway_run_forever_and_stop() -> None:
    """Test run_forever can be stopped with stop()."""
    import threading
    import time

    transport = MeshtasticTransport(InMemoryRadio("gateway"))
    gateway = MeshtasticGateway(
        transport=transport,
        api_base_url="http://localhost:8000",
    )

    # Run gateway in thread (daemon to prevent hanging if test fails)
    def run_gateway():
        gateway.run_forever(poll_interval=0.1)

    gateway_thread = threading.Thread(target=run_gateway, daemon=True)
    gateway_thread.start()

    try:
        # Let it run briefly
        time.sleep(0.3)

        # Stop gateway
        gateway.stop()

        # Thread should exit
        gateway_thread.join(timeout=1.0)
        assert not gateway_thread.is_alive()
        assert gateway._running is False
    finally:
        # Ensure cleanup in case of failures or timeouts
        if gateway._running:
            gateway.stop()
        if gateway_thread.is_alive():
            gateway_thread.join(timeout=1.0)


def test_gateway_run_operation_async_execution() -> None:
    """Test _run_operation executes async operation."""
    transport = MeshtasticTransport(InMemoryRadio("gateway"))
    gateway = MeshtasticGateway(
        transport=transport,
        api_base_url="http://localhost:8000",
    )

    # Create a mock operation module with async run function
    mock_module = MagicMock()
    async_result = {"test": "result"}

    async def mock_run(client, envelope, data):
        return async_result

    mock_module.run = mock_run

    envelope = MessageEnvelope(
        id="async-test",
        type="request",
        command="test",
        data={"input": "data"},
    )

    result = gateway._run_operation(mock_module, {"input": "data"}, envelope)

    assert result == async_result


def test_gateway_handle_request_operation_exception() -> None:
    """Test _handle_request handles operation exceptions gracefully."""
    transport = MeshtasticTransport(InMemoryRadio("gateway"))
    gateway = MeshtasticGateway(
        transport=transport,
        api_base_url="http://localhost:8000",
    )

    envelope = MessageEnvelope(
        id="exception-test",
        type="request",
        command="test_echo",
        data={},
    )

    # Mock the operation to raise an exception
    with patch.object(gateway, "_run_operation") as mock_run:
        mock_run.side_effect = RuntimeError("Operation failed")

        response = gateway._handle_request(envelope)

        assert response.id == envelope.id
        assert response.type == "error"
        assert response.data is not None
        assert "Operation failed" in response.data["error"]


def test_gateway_blocks_in_progress_duplicate() -> None:
    """Gateway should ignore a request whose semantic key is already leased."""
    bus = InMemoryRadioBus()
    sender_transport = MeshtasticTransport(InMemoryRadio("sender", bus))
    gateway_transport = MeshtasticTransport(InMemoryRadio("gateway", bus))

    gateway = MeshtasticGateway(
        transport=gateway_transport,
        api_base_url="http://localhost:8000",
    )

    envelope = MessageEnvelope(
        id="task-in-progress",
        type="request",
        command="start_task",
        data={"task_id": "TASK-123"},
    )

    # Manually acquire lease to simulate in-progress operation
    dedupe_keys = gateway_transport.build_dedupe_keys("sender", envelope)
    assert dedupe_keys.semantic is not None
    assert gateway_transport.deduper.acquire_lease(dedupe_keys.semantic) is True

    sender_transport.send_message(envelope, "gateway")

    with patch.object(gateway, "_handle_request") as mock_handle:
        gateway.run_once(timeout=0.5)
        mock_handle.assert_not_called()


def test_gateway_propagates_correlation_id() -> None:
    """Responses should include the incoming correlation_id."""
    transport = MeshtasticTransport(InMemoryRadio("gateway"))
    gateway = MeshtasticGateway(
        transport=transport,
        api_base_url="http://localhost:8000",
    )

    envelope = MessageEnvelope(
        id="corr-test",
        type="request",
        command="test_echo",
        correlation_id="corr-123",
        data={"msg": "hello"},
    )

    response = gateway._handle_request(envelope)

    assert response.correlation_id == "corr-123"
    assert response.id == envelope.id


def test_gateway_sends_error_and_releases_on_exception() -> None:
    """Gateway should send an error response and release lease when an exception occurs."""
    bus = InMemoryRadioBus()
    sender_transport = MeshtasticTransport(InMemoryRadio("sender", bus))
    gateway_transport = MeshtasticTransport(InMemoryRadio("gateway", bus))

    gateway = MeshtasticGateway(
        transport=gateway_transport,
        api_base_url="http://localhost:8000",
    )

    envelope = MessageEnvelope(
        id="error-case",
        type="request",
        command="test_echo",
        correlation_id="corr-exc",
        data={"msg": "boom"},
    )

    sender_transport.send_message(envelope, "gateway")

    with patch.object(gateway, "_handle_request") as mock_handle:
        mock_handle.side_effect = RuntimeError("fail-me")
        gateway.run_once(timeout=0.5)

    # Client should receive an error response
    sender, response = sender_transport.receive_message(timeout=0.5)
    assert sender == "gateway"
    assert response is not None
    assert response.type == "error"
    assert response.correlation_id == "corr-exc"

    # Lease should be released after error handling
    dedupe_keys = gateway_transport.build_dedupe_keys("sender", envelope)
    assert gateway_transport.deduper.acquire_lease(
        dedupe_keys.semantic or dedupe_keys.correlation or dedupe_keys.message
    )


def test_gateway_numeric_sender_waits_for_discovery() -> None:
    """Test gateway waits for node discovery when sender is numeric ID."""
    bus = InMemoryRadioBus()
    sender_transport = MeshtasticTransport(InMemoryRadio("123456789", bus))  # Numeric ID
    gateway_transport = MeshtasticTransport(InMemoryRadio("gateway", bus))

    gateway = MeshtasticGateway(
        transport=gateway_transport,
        api_base_url="http://localhost:8000",
    )

    envelope = MessageEnvelope(
        id="numeric-sender",
        type="request",
        command="test_echo",
        data={"msg": "test"},
    )

    # Send from numeric node ID
    sender_transport.send_message(envelope, "gateway")

    # Patch time.sleep in the gateway module specifically
    with patch("atlas_meshtastic_bridge.gateway.time.sleep") as mock_sleep:
        gateway.run_once(timeout=0.5)
        # Check that sleep was called with 1.5s for node discovery
        # There should be a call with 1.5 seconds
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert 1.5 in sleep_calls, f"Expected sleep(1.5) but got {sleep_calls}"


def test_gateway_integration_with_client_request() -> None:
    """Test gateway processing a real request and sending response."""
    bus = InMemoryRadioBus()
    client_transport = MeshtasticTransport(InMemoryRadio("client", bus))
    gateway_transport = MeshtasticTransport(InMemoryRadio("gateway", bus))

    gateway = MeshtasticGateway(
        transport=gateway_transport,
        api_base_url="http://localhost:8000",
    )

    # Send request from client
    request = MessageEnvelope(
        id="integration-test",
        type="request",
        command="test_echo",
        data={"payload": "integration test data"},
    )
    client_transport.send_message(request, "gateway")

    # Gateway processes request
    gateway.run_once(timeout=1.0)

    # Client receives response
    sender, response = client_transport.receive_message(timeout=1.0)

    assert sender == "gateway"
    assert response is not None
    assert response.id == request.id
    assert response.type == "response"
    assert response.data is not None
    assert response.data["result"]["echo"] == {"payload": "integration test data"}


def test_gateway_handles_empty_data() -> None:
    """Test gateway handles requests with None data."""
    transport = MeshtasticTransport(InMemoryRadio("gateway"))
    gateway = MeshtasticGateway(
        transport=transport,
        api_base_url="http://localhost:8000",
    )

    envelope = MessageEnvelope(
        id="empty-data",
        type="request",
        command="test_echo",
        data=None,
    )

    response = gateway._handle_request(envelope)

    assert response.type == "response"
    assert response.data is not None
    assert "result" in response.data
