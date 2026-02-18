# Atlas Meshtastic Bridge

Reliable offline access to Atlas Command over Meshtastic radios. The bridge runs in two modes:

- **Gateway** - connected to Atlas Command over IP. It receives Meshtastic requests, calls the HTTP API, and returns responses over radio.
- **Client** - runs next to a field asset. It issues Atlas Command requests via the gateway and renders the responses locally.

> The protocol and chunking design are described in `docs/SYSTEMS_DESIGN.md`. This README focuses on day-to-day setup, usage, and troubleshooting.

## Reliability guarantees

- Application-level ACKs are emitted for every reassembled message; senders track pending messages until ACKed.
- Outgoing messages are durably spooled to disk (JSON file) and retried with exponential backoff + jitter until acknowledged.
- Pending messages are replayed automatically after restarts; gateways flush the outbox each poll cycle and clients flush before sending.
- ACK envelopes are filtered from application handlers so existing client/gateway flows remain unchanged.
- Spool location is configurable via `--spool-path` (default: `~/.atlas_meshtastic_spool.json`).

## Payload limits

- **Chunk**: the smallest on-air packet sent over Meshtastic (what the transport already splits and ACKs today).
- Current behavior: the hardware harness enforces a 10 KB limit for object uploads. Larger transfers are currently disabled; use the Atlas HTTP API instead.
- Until a segment layer ships, use a staged reliability loop for big transfers: split into chunks, send them once, emit a tiny completion marker, have the receiver respond with missing chunk indices, resend only the gaps, then repeat the completion/missing/resend cycle until nothing is missing.
- Future plan: reintroduce a proper segment layer (segment = intermediate slice, chunk = on-air packet) with gateway-side reassembly. This is not implemented yet.

## Prerequisites

- Python 3.10+
- Atlas Command reachable from the gateway (HTTPS recommended)
- Meshtastic radios flashed with current firmware
- Optional: virtual (in-memory) radio for local testing

Install the bridge as a standalone package (and optionally meshtastic-python for real radios):

```bash
cd Atlas_Client_SDKs/connection_packages/atlas_meshtastic_bridge
pip install -e .[meshtastic]        # includes meshtastic-python
# or, for simulation-only workflows without hardware drivers:
pip install -e .
```

## Meshtastic hardware setup

1. Flash both radios with the same firmware and channel settings. Verify they can message each other using the Meshtastic app.
2. Connect the gateway radio to the machine that can reach Atlas Command over IP.
3. Note the serial port for each device:
   - Linux: `/dev/ttyUSB0`, `/dev/ttyACM0`, or `dmesg | grep tty`
   - macOS: `/dev/cu.usbserial-*`
   - Windows: `COM3`, `COM4`, etc.
4. Recommended radio config:
   - Same channel name/psk on all nodes
   - `hop_limit` and `power` appropriate for your mesh size
   - Unique, meaningful node IDs (set via Meshtastic app)
5. Run with `--radio-port` pointing at the serial device. Use `--simulate-radio` to bypass hardware during development.

## Configuration

CLI flags (client and gateway):

| Flag | Description |
| --- | --- |
| `--mode {gateway,client}` | Run as gateway or client (required). |
| `--gateway-node-id` | Meshtastic node ID of the gateway (required). |
| `--api-base-url` | Atlas Command base URL. Required by the CLI; gateway uses it for HTTP calls (clients must still supply because the flag is required). |
| `--api-token` | Atlas Command bearer token (gateway mode, optional). |
| `--timeout` | Client request timeout in seconds (default: 5). |
| `--simulate-radio` | Use in-memory radio instead of hardware. |
| `--radio-port` | Serial port path (hardware mode). |
| `--node-id` | Override local node ID (default: `gateway` or `client`). |
| `--command` | Client command to run (client mode). |
| `--data` | JSON payload for the command (client mode). |
| `--log-level` | Logging level (default: `INFO`). |

Environment variables (gateway):

| Variable | Purpose |
| --- | --- |
| `ATLAS_API_BASE_URL` | Convenience only; the bridge does **not** read this directly. Export it and pass via `--api-base-url \"$ATLAS_API_BASE_URL\"`. |
| `ATLAS_API_TOKEN` | Convenience only; the bridge does **not** read this directly. Export it and pass via `--api-token \"$ATLAS_API_TOKEN\"`. |

## Quick start (simulated radios)

Terminal 1 - start gateway:

```bash
python -m atlas_meshtastic_bridge.cli \
  --mode gateway \
  --gateway-node-id gw-1 \
  --api-base-url http://localhost:8000 \
  --api-token "$ATLAS_API_TOKEN" \
  --simulate-radio \
  --node-id gw-1
```

Terminal 2 - run a client request:

```bash
python -m atlas_meshtastic_bridge.cli \
  --mode client \
  --gateway-node-id gw-1 \
  --api-base-url http://localhost:8000 \
  --simulate-radio \
  --node-id field-1 \
  --command list_entities \
  --data '{"limit":5}'
```

## Usage examples

### Entity registration / creation

Entity creation is performed over the HTTP API (the mesh bridge keeps payloads small). Register the asset via HTTP first, then use the bridge for telemetry and tasking:

```bash
curl -X POST "$ATLAS_API_BASE_URL/entities" \
  -H "Authorization: Bearer $ATLAS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id":"DRONE-001","entity_type":"asset","subtype":"uav","alias":"DRONE-001"}'
```

### Check-in workflow (over Meshtastic)

1. Ensure the entity exists (HTTP as above).
2. Send a check-in from the asset:

```bash
python -m atlas_meshtastic_bridge.cli \
  --mode client \
  --gateway-node-id gw-1 \
  --simulate-radio \
  --command checkin_entity \
  --data '{"entity_id":"DRONE-001","latitude":40.0,"longitude":-105.0}'
```

3. Fetch outstanding tasks for the entity:

```bash
python -m atlas_meshtastic_bridge.cli \
  --mode client \
  --gateway-node-id gw-1 \
  --simulate-radio \
  --command get_tasks_by_entity \
  --data '{"entity_id":"DRONE-001","limit":5}'
```

4. Report progress or telemetry:

```bash
python -m atlas_meshtastic_bridge.cli \
  --mode client \
  --gateway-node-id gw-1 \
  --simulate-radio \
  --command update_telemetry \
  --data '{"entity_id":"DRONE-001","altitude_m":1200,"speed_m_s":14}'
```

### Task execution (start / complete / fail)

```bash
# Start a task
python -m atlas_meshtastic_bridge.cli --mode client --gateway-node-id gw-1 \
  --simulate-radio --command start_task --data '{"task_id":"TASK-123"}'

# Complete a task with result data
python -m atlas_meshtastic_bridge.cli --mode client --gateway-node-id gw-1 \
  --simulate-radio --command complete_task --data '{"task_id":"TASK-123","result":{"summary":"scan complete"}}'
```

### Object download

Request object metadata or bytes (small payloads only):

```bash
python -m atlas_meshtastic_bridge.cli --mode client --gateway-node-id gw-1 \
  --simulate-radio --command get_object \
  --data '{"object_id":"OBJ-1","download":true}'
```

If `download` is omitted or false, only metadata is returned.

### Object upload

Large uploads are intentionally not sent over Meshtastic. Use the Atlas Command HTTP API to obtain a presigned upload URL, upload the file via HTTPS, and then reference the object by ID in subsequent mesh requests.

### Change feed / incremental sync

Fetch changes since an RFC3339 timestamp:

```bash
python -m atlas_meshtastic_bridge.cli --mode client --gateway-node-id gw-1 \
  --simulate-radio --command get_changed_since \
  --data '{"since":"2025-01-01T00:00:00Z","limit_per_type":50}'
```

## End-to-end workflow example

1. Register entity via HTTP.
2. Start gateway (hardware or simulated) pointed at Atlas Command.
3. Client check-in over Meshtastic; gateway forwards to Atlas Command.
4. Client requests tasks; gateway responds with pending assignments.
5. Client downloads any referenced objects (metadata/bytes) as needed.
6. Client reports task status (start/complete/fail) and telemetry updates.

## Command reference

| Command | Description | Payload keys |
| --- | --- | --- |
| `list_entities` | List entities with pagination. | `limit`, `offset` |
| `get_entity` | Fetch entity by ID. | `entity_id` |
| `get_entity_by_alias` | Fetch entity by alias. | `alias` |
| `checkin_entity` | Check in an entity with optional telemetry and task filters. | `entity_id`, telemetry fields, optional `status_filter`, `limit`, `since`, `fields` |
| `update_telemetry` | Update entity telemetry. | `entity_id`, telemetry fields (`latitude`, `longitude`, `altitude_m`, `speed_m_s`, `heading_deg`) |
| `list_tasks` | List tasks. | `limit`, optional `status` |
| `get_task` | Fetch task by ID. | `task_id` |
| `get_tasks_by_entity` | Tasks scoped to an entity. | `entity_id`, `limit` |
| `start_task` | Mark a task as started. | `task_id` |
| `complete_task` | Mark task complete. | `task_id`, optional `result` |
| `fail_task` | Mark task failed. | `task_id`, optional `error_message`, `error_details` |
| `list_objects` | List objects. | `limit`, `offset` |
| `get_object` | Get object metadata or bytes. | `object_id`, optional `download` |
| `get_objects_by_entity` | Objects linked to an entity. | `entity_id`, optional `limit` |
| `get_objects_by_task` | Objects linked to a task. | `task_id`, optional `limit` |
| `get_changed_since` | Incremental change feed (includes deleted_entities/deleted_tasks/deleted_objects; ~1h in-memory TTL). | `since`, `limit_per_type` |
| `test_echo` | Echo payload for connectivity testing. | free-form |

## Troubleshooting

- **No response from gateway**: Confirm the gateway process is running, radio IDs match `--gateway-node-id`, and Atlas Command is reachable at `--api-base-url` (check `/health`).
- **Serial port errors**: Verify the port path and permissions (`sudo usermod -a -G dialout $USER` on Linux). Try `--simulate-radio` to isolate radio issues.
- **Large payloads dropped**: Messages are chunked to fit Meshtastic limits (~200 bytes). Avoid sending large JSON or binary content; use HTTP uploads instead.
- **Duplicate or missing responses**: Ensure both radios share the same channel/PSK and that clocks are roughly in sync. The CLI generates a fresh UUID for every request; custom integrations should do the same and reuse that UUID when retrying so deduplication works as expected.
- **Timeouts**: Increase `--timeout` for slow links. Poor RF conditions may require retries on the client side.

## Where to go next

- Protocol details: `docs/SYSTEMS_DESIGN.md`
- Code reference: `atlas_meshtastic_bridge.gateway` and `atlas_meshtastic_bridge.transport`
- Atlas Command HTTP client: `connection_packages/atlas_asset_http_client_python`
