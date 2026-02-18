"""Unit tests for MeshtasticClient."""

import pytest
from atlas_meshtastic_bridge.client import MeshtasticClient
from atlas_meshtastic_bridge.message import MessageEnvelope
from atlas_meshtastic_bridge.transport import (
    InMemoryRadio,
    InMemoryRadioBus,
    MeshtasticTransport,
)


def test_client_initialization() -> None:
    """Test MeshtasticClient initialization."""
    transport = MeshtasticTransport(InMemoryRadio("client"))
    client = MeshtasticClient(transport, gateway_node_id="!gateway123")

    assert client.transport == transport
    assert client.gateway_node_id == "!gateway123"


def test_client_send_request_success() -> None:
    """Test sending a request and receiving a response."""
    bus = InMemoryRadioBus()
    client_transport = MeshtasticTransport(InMemoryRadio("client", bus))
    gateway_transport = MeshtasticTransport(InMemoryRadio("gateway", bus))

    client = MeshtasticClient(client_transport, gateway_node_id="gateway")

    # Simulate gateway in another thread (we'll do it synchronously for testing)
    import threading

    def gateway_handler():
        # Receive request
        sender, request = gateway_transport.receive_message(timeout=2.0)
        if request:
            # Send response
            response = MessageEnvelope(
                id=request.id,
                type="response",
                command=request.command,
                data={"result": "success"},
            )
            gateway_transport.send_message(response, sender)

    gateway_thread = threading.Thread(target=gateway_handler)
    gateway_thread.start()

    # Send request
    response = client.send_request(
        command="list_entities",
        data={"limit": 10},
        timeout=3.0,
    )

    gateway_thread.join(timeout=5.0)
    assert not gateway_thread.is_alive()

    assert response is not None
    assert response.type == "response"
    assert response.command == "list_entities"
    assert response.data == {"result": "success"}


def test_client_send_request_timeout() -> None:
    """Test that send_request raises TimeoutError when no response is received."""
    transport = MeshtasticTransport(InMemoryRadio("client"))
    client = MeshtasticClient(transport, gateway_node_id="gateway")

    # No gateway to respond
    with pytest.raises(TimeoutError, match="No response"):
        client.send_request(
            command="test_command",
            data={},
            timeout=0.5,
            max_retries=0,
        )


def test_client_send_request_retry() -> None:
    """Test retry mechanism on timeout."""
    bus = InMemoryRadioBus()
    client_transport = MeshtasticTransport(InMemoryRadio("client", bus))
    gateway_transport = MeshtasticTransport(InMemoryRadio("gateway", bus))

    client = MeshtasticClient(client_transport, gateway_node_id="gateway")

    # Track retry attempts
    attempt_count = [0]

    def gateway_handler():
        # Only respond on second attempt (ignore first to force retry)
        # Listen for requests but only respond to the second one
        while True:
            sender, request = gateway_transport.receive_message(timeout=3.0)
            if request:
                attempt_count[0] += 1
                # Respond on second attempt
                if attempt_count[0] == 2:
                    response = MessageEnvelope(
                        id=request.id,
                        type="response",
                        command=request.command,
                        data={"result": "retry success"},
                    )
                    gateway_transport.send_message(response, sender)
                    return  # Exit immediately after sending response
                # First attempt: ignore (don't respond to force retry)

    import threading

    gateway_thread = threading.Thread(target=gateway_handler)
    gateway_thread.start()

    # Send request with timeout that allows retry
    response = client.send_request(
        command="test_retry",
        data={},
        timeout=1.0,
        max_retries=2,
    )

    gateway_thread.join(timeout=5.0)
    assert not gateway_thread.is_alive()

    assert response is not None
    assert response.data == {"result": "retry success"}
    # Should have seen exactly 2 attempts (first ignored, second responded)
    assert attempt_count[0] == 2


def test_client_send_request_error_response() -> None:
    """Test handling error responses from gateway."""
    bus = InMemoryRadioBus()
    client_transport = MeshtasticTransport(InMemoryRadio("client", bus))
    gateway_transport = MeshtasticTransport(InMemoryRadio("gateway", bus))

    client = MeshtasticClient(client_transport, gateway_node_id="gateway")

    def gateway_handler():
        sender, request = gateway_transport.receive_message(timeout=2.0)
        if request:
            # Send error response
            error_response = MessageEnvelope(
                id=request.id,
                type="error",
                command=request.command,
                data={"error": "Something went wrong"},
            )
            gateway_transport.send_message(error_response, sender)

    import threading

    gateway_thread = threading.Thread(target=gateway_handler)
    gateway_thread.start()

    # Send request
    response = client.send_request(
        command="failing_command",
        data={},
        timeout=2.0,
    )

    gateway_thread.join()

    assert response is not None
    assert response.type == "error"
    assert response.data is not None
    assert response.data["error"] == "Something went wrong"


def test_client_send_request_ignores_wrong_id() -> None:
    """Test that client ignores responses with wrong request ID."""
    bus = InMemoryRadioBus()
    client_transport = MeshtasticTransport(InMemoryRadio("client", bus))
    gateway_transport = MeshtasticTransport(InMemoryRadio("gateway", bus))

    client = MeshtasticClient(client_transport, gateway_node_id="gateway")

    def gateway_handler():
        sender, request = gateway_transport.receive_message(timeout=2.0)
        if request:
            # Send response with wrong ID
            wrong_response = MessageEnvelope(
                id="wrong-id-12345",
                type="response",
                command=request.command,
                data={"result": "wrong"},
            )
            gateway_transport.send_message(wrong_response, sender)

            # Send correct response after delay
            import time

            time.sleep(0.3)
            correct_response = MessageEnvelope(
                id=request.id,
                type="response",
                command=request.command,
                data={"result": "correct"},
            )
            gateway_transport.send_message(correct_response, sender)

    import threading

    gateway_thread = threading.Thread(target=gateway_handler)
    gateway_thread.start()

    # Send request
    response = client.send_request(
        command="test_id_match",
        data={},
        timeout=2.0,
    )

    gateway_thread.join()

    # Should receive the correct response
    assert response is not None
    assert response.data is not None
    assert response.data["result"] == "correct"


def test_client_send_request_ignores_wrong_type() -> None:
    """Test that client ignores messages that are not response or error types."""
    bus = InMemoryRadioBus()
    client_transport = MeshtasticTransport(InMemoryRadio("client", bus))
    gateway_transport = MeshtasticTransport(InMemoryRadio("gateway", bus))

    client = MeshtasticClient(client_transport, gateway_node_id="gateway")

    def gateway_handler():
        sender, request = gateway_transport.receive_message(timeout=2.0)
        if request:
            # Send request type (should be ignored)
            wrong_type = MessageEnvelope(
                id=request.id,
                type="request",  # Wrong type
                command=request.command,
                data={"result": "wrong type"},
            )
            gateway_transport.send_message(wrong_type, sender)

            # Send correct response
            import time

            time.sleep(0.2)
            correct_response = MessageEnvelope(
                id=request.id,
                type="response",
                command=request.command,
                data={"result": "correct type"},
            )
            gateway_transport.send_message(correct_response, sender)

    import threading

    gateway_thread = threading.Thread(target=gateway_handler)
    gateway_thread.start()

    # Send request
    response = client.send_request(
        command="test_type_filter",
        data={},
        timeout=2.0,
    )

    gateway_thread.join()

    # Should receive the correct response
    assert response is not None
    assert response.data is not None
    assert response.data["result"] == "correct type"


def test_client_send_request_with_data() -> None:
    """Test sending request with complex data payload."""
    bus = InMemoryRadioBus()
    client_transport = MeshtasticTransport(InMemoryRadio("client", bus))
    gateway_transport = MeshtasticTransport(InMemoryRadio("gateway", bus))

    client = MeshtasticClient(client_transport, gateway_node_id="gateway")

    request_data = {
        "entity_id": "123",
        "filters": {"status": "active", "priority": "high"},
        "pagination": {"limit": 50, "offset": 0},
    }

    received_data = [None]

    def gateway_handler():
        sender, request = gateway_transport.receive_message(timeout=2.0)
        if request:
            received_data[0] = request.data
            response = MessageEnvelope(
                id=request.id,
                type="response",
                command=request.command,
                data={"result": "received"},
            )
            gateway_transport.send_message(response, sender)

    import threading

    gateway_thread = threading.Thread(target=gateway_handler)
    gateway_thread.start()

    # Send request with data
    response = client.send_request(
        command="get_tasks_by_entity",
        data=request_data,
        timeout=2.0,
    )

    gateway_thread.join()

    assert response is not None
    assert received_data[0] == request_data
