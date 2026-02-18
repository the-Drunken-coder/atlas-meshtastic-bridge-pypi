"""Unit tests for MessageEnvelope and chunking functions."""

import json
from pathlib import Path

from atlas_meshtastic_bridge.message import (
    MessageEnvelope,
    chunk_envelope,
    parse_chunk,
    reconstruct_message,
)


def test_message_envelope_creation() -> None:
    """Test creating a MessageEnvelope."""
    envelope = MessageEnvelope(
        id="test-id-123",
        type="request",
        command="list_entities",
        data={"limit": 10},
        meta={"timestamp": "2023-01-01"},
    )

    assert envelope.id == "test-id-123"
    assert envelope.type == "request"
    assert envelope.command == "list_entities"
    assert envelope.data == {"limit": 10}
    assert envelope.meta == {"timestamp": "2023-01-01"}


def test_message_envelope_to_dict() -> None:
    """Test converting MessageEnvelope to dict."""
    envelope = MessageEnvelope(
        id="test-id",
        type="response",
        command="get_entity",
        data={"result": "success"},
    )

    result = envelope.to_dict()

    assert result["id"] == "test-id"
    assert result["type"] == "response"
    assert result["command"] == "get_entity"
    assert result["data"] == {"result": "success"}
    assert "meta" not in result


def test_message_envelope_from_dict() -> None:
    """Test creating MessageEnvelope from dict."""
    payload = {
        "id": "test-id",
        "type": "error",
        "command": "unknown",
        "data": {"error": "not found"},
        "meta": {"code": 404},
        "correlation_id": "corr-1",
    }

    envelope = MessageEnvelope.from_dict(payload)

    assert envelope.id == "test-id"
    assert envelope.type == "error"
    assert envelope.command == "unknown"
    assert envelope.data == {"error": "not found"}
    assert envelope.meta == {"code": 404}
    assert envelope.correlation_id == "corr-1"


def test_chunk_envelope_single_chunk() -> None:
    """Test chunking a small envelope that fits in one chunk."""
    envelope = MessageEnvelope(
        id="short-message",
        type="request",
        command="ping",
        data={"msg": "hi"},
    )

    chunks = chunk_envelope(envelope, segment_size=120)

    assert len(chunks) == 1
    flags, short_id, seq, total, data = parse_chunk(chunks[0])
    assert flags == 0
    assert short_id == "short-me"
    assert seq == 1
    assert total == 1
    assert data


def test_chunk_envelope_multiple_chunks() -> None:
    """Test chunking a large envelope into multiple chunks."""
    # Create a large payload
    large_data = {"payload": "x" * 500}
    envelope = MessageEnvelope(
        id="large-message-id",
        type="request",
        command="test",
        data=large_data,
    )

    chunks = chunk_envelope(envelope, segment_size=60)

    assert len(chunks) > 1
    # All chunks should have the same short ID
    _, short_id, _, total, _ = parse_chunk(chunks[0])
    assert short_id == "large-me"
    for chunk in chunks:
        _, chunk_id, _, chunk_total, _ = parse_chunk(chunk)
        assert chunk_id == short_id
        assert chunk_total == total

    # Check sequence numbers
    for i, chunk in enumerate(chunks):
        _, _, seq, total_chunks, _ = parse_chunk(chunk)
        assert seq == i + 1
        assert total_chunks == len(chunks)


def test_reconstruct_message() -> None:
    """Test reconstructing a message from segments."""
    original = MessageEnvelope(
        id="test-reconstruct",
        type="request",
        command="get_task",
        correlation_id="corr-123",
        data={"task_id": 42, "details": "x" * 100},
    )

    chunks = chunk_envelope(original, segment_size=50)
    segments = [parse_chunk(chunk)[4] for chunk in chunks]

    reconstructed = reconstruct_message(segments)

    assert reconstructed.id == original.id
    assert reconstructed.type == original.type
    assert reconstructed.command == original.command
    assert reconstructed.correlation_id == original.correlation_id
    assert reconstructed.data == original.data


def test_chunk_and_reconstruct_roundtrip() -> None:
    """Test that chunking and reconstructing preserves the message."""
    original = MessageEnvelope(
        id="roundtrip-test-id",
        type="response",
        command="list_tasks",
        data={
            "tasks": [
                {"id": 1, "name": "Task 1"},
                {"id": 2, "name": "Task 2"},
            ]
        },
        meta={"count": 2},
    )

    chunks = chunk_envelope(original, segment_size=40)
    segments = [parse_chunk(chunk)[4] for chunk in chunks]
    reconstructed = reconstruct_message(segments)

    assert reconstructed.id == original.id
    assert reconstructed.type == original.type
    assert reconstructed.command == original.command
    assert reconstructed.data == original.data
    assert reconstructed.meta == original.meta


def test_chunk_envelope_compression() -> None:
    """Test that chunking includes compression."""
    # Repetitive data should compress well
    envelope = MessageEnvelope(
        id="compress-test",
        type="request",
        command="test",
        data={"pattern": "abc" * 100},
    )

    chunks = chunk_envelope(envelope, segment_size=120)

    # The compressed data should be present
    total_chunk_data_len = sum(len(parse_chunk(chunk)[4]) for chunk in chunks)

    # Compressed + base64 encoded data should be valid
    assert total_chunk_data_len > 0
    # We can't guarantee compression ratio, but data should be valid
    for chunk in chunks:
        data = parse_chunk(chunk)[4]
        assert isinstance(data, (bytes, bytearray))
        assert len(data) > 0


def test_payload_roundtrip_fixture() -> None:
    """Encode/decode fixture payloads and ensure normalization is stable."""
    base_dir = Path(__file__).parent / "fixtures"
    payload_path = base_dir / "payload_entity.json"
    expected_path = base_dir / "payload_entity_expected.json"

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    expected = json.loads(expected_path.read_text(encoding="utf-8"))

    envelope = MessageEnvelope(
        id="fixture-test",
        type="response",
        command="list_entities",
        data={"result": [payload]},
    )

    chunks = chunk_envelope(envelope, segment_size=120)
    segments = [parse_chunk(chunk)[4] for chunk in chunks]
    reconstructed = reconstruct_message(segments)

    assert reconstructed.data == {"result": [expected]}
