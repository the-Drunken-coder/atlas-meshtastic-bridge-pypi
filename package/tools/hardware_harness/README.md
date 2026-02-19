# Meshtastic Bridge Hardware Harness

This directory contains a **manual testing harness** for the Atlas Meshtastic bridge. It is **not**
packaged with the library; it is intended for developers to exercise the bridge against real radios.

## Prerequisites

- Python 3.10+
- `atlas-asset-client>=0.3.0`
- `meshtastic>=2.3.0` (required for real radios)
- Two Meshtastic radios connected over USB (or simulation mode)

## Assumptions

- Two Meshtastic radios are plugged into the laptop running this harness.
- The Atlas Command API is reachable at `http://localhost:8000/` (adjustable via CLI).
- `meshtastic` and `atlas_asset_http_client_python` are installed so the gateway can talk to
  both the radio and the HTTP API.

## Quick start

```bash
cd Atlas_Client_SDKs/connection_packages/atlas_meshtastic_bridge

# Optional but safer: keep the API token out of the process list
export ATLAS_API_TOKEN=******  # harness will read this automatically

# Edit tools/hardware_harness/config.json (auto-created on first run) to set ports, node IDs, etc.
python tools/hardware_harness/dual_radio_harness.py
```

Config file (JSON, default path: `tools/hardware_harness/config.json`):

```json
{
  "gateway_port": "/dev/ttyUSB0",
  "client_port": "/dev/ttyUSB1",
  "gateway_node_id": "!abcdef12",
  "client_node_id": "!1234abcd",
  "api_base_url": "http://localhost:8000/",
  "api_token": null,
  "mode": "general",
  "reliability_method": null,
  "modem_preset": null,
  "simulate": false,
  "timeout": 90.0,
  "retries": 2,
  "log_level": "INFO",
  "post_response_quiet": 10.0,
  "post_response_timeout": 150.0,
  "loop": false,
  "clear_spool": false,
  "spool_dir": "~/.atlas_meshtastic_harness",
  "transport_overrides": {}
}
```

When the harness starts it will:

1. Spin up a gateway process using the gateway radio and point it at the Atlas API.
2. Connect a client instance to the second radio.
3. Present a terminal menu so you can choose a command (echo, entity/task operations, custom JSON).
4. Send the client request over the mesh; the gateway forwards to Atlas and returns the response.

Press `q` to exit the harness; it will shut down both radios and the gateway thread.

## Notes

- Use the `simulate` config key to run without hardware; this is helpful for dry runs but will not
  hit real radios.
- Spool files are stored under `~/.atlas_meshtastic_harness/` to avoid interfering with other runs.
  The harness uses separate files in that directory (for example `gateway_spool.json` and
  `client_spool.json`).
- For tokens, prefer exporting `ATLAS_API_TOKEN` so it is not visible in the process list; use
  `--api-token` only when necessary and in trusted environments.
- If the gateway reports that `atlas_asset_http_client_python` is missing, install it in your
  environment before retrying.
- The harness currently enforces a **10 KB limit** for object uploads. Larger transfers are disabled; use the Atlas
  HTTP API instead. Future work will revisit a full segmentation/reassembly flow once the gateway supports it.
