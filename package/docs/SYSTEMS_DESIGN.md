# Atlas Meshtastic Bridge

This package bridges Atlas Command HTTP operations over Meshtastic radio links.

- Gateway mode: receives radio requests, executes Atlas HTTP operations, returns radio responses.
- Client mode: sends request envelopes to the gateway and waits for matching responses.

For quick start and troubleshooting, see `../README.md`.

## Protocol Overview

### 1. Envelope

Messages are encoded as envelope objects, then serialized with MessagePack and compressed with Zstandard.

```json
{
  "id": "message-id",
  "type": "request|response|error|ack",
  "command": "list_entities",
  "priority": 10,
  "correlation_id": "optional",
  "data": { "limit": 5 },
  "meta": {}
}
```

Notes:

- `command` values are snake_case operation names (for example `list_entities`, `get_task`).
- `priority` is included in the envelope model; lower numbers are higher priority.
- Key aliasing/compaction is applied before transport and reversed on decode.

### 2. Binary Chunk Header

Each chunk has a fixed 16-byte header:

- Magic: `MB` (2 bytes)
- Version: `1` (1 byte)
- Flags: bitfield (ACK=`0x01`, NACK=`0x02`)
- Message ID prefix: first 8 bytes of envelope ID (padded)
- Sequence: uint16 (1-based)
- Total: uint16

### 3. Chunking and Reassembly

- Chunks are sized to stay under the transport hard limit (`MAX_CHUNK_SIZE = 230` bytes).
- Transport starts with a segment size around 200 bytes and can auto-reduce if chunks exceed the limit.
- Reassembly uses TTL-based buckets (`120s` base, extended per chunk, capped at `600s`).

### 4. Reliability and ACK/NACK

- Default strategy is windowed selective repeat (`window`).
- After send, sender can request missing chunk bitmap; receiver responds with NACK gaps or `all_received`.
- Single-chunk messages skip the bitmap request optimization.
- Alternative strategies exist (`simple`, `stage`, `window_fec`), selected via runtime config/env.
- ACK control payloads can contain control strings (for example `all_received|<message_id>`, `bitmap_req|<message_id>`) and are not limited to raw IDs.

### 5. Dedupe

- Gateway dedupes requests before API execution using message/semantic keys and optional lease windows.
- Clients should retry using the same request `id` for idempotent replay behavior.

## Running the Bridge

Gateway example:

```bash
python -m atlas_meshtastic_bridge.cli \
  --mode gateway \
  --gateway-node-id gw-1 \
  --api-base-url http://localhost:8000 \
  --api-token "${ATLAS_TOKEN}" \
  --node-id gw-1 \
  --simulate-radio
```

Client example:

```bash
python -m atlas_meshtastic_bridge.cli \
  --mode client \
  --gateway-node-id gw-1 \
  --api-base-url http://localhost:8000 \
  --command list_entities \
  --data '{"limit":5}' \
  --simulate-radio \
  --node-id field-1
```

Use `--radio-port` for hardware transport instead of `--simulate-radio`.

## Testing

```bash
cd Atlas_Client_SDKs/connection_packages
python -m pytest atlas_meshtastic_bridge/tests/test_message_chunking.py -k chunk
```
