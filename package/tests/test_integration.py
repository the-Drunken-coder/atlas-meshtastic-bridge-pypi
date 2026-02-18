"""Integration test using actual atlas_meshtastic_bridge functionality with two radios.

This script tests the full bridge functionality:
- COM8 acts as the client (sends API requests)
- COM9 acts as the gateway (receives requests, calls API, sends responses)
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import time
from pathlib import Path

# Add connection_packages to path for atlas_meshtastic_bridge imports
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from atlas_meshtastic_bridge.cli import build_radio
from atlas_meshtastic_bridge.config import BridgeConfig
from atlas_meshtastic_bridge.transport import MeshtasticTransport

# Configure logging for both client and gateway
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

LOGGER = logging.getLogger(__name__)


def get_node_id(port: str) -> str:
    """Get the node ID for a radio on the given port."""
    try:
        from meshtastic import serial_interface

        interface = serial_interface.SerialInterface(port)
        time.sleep(1)
        my_info = interface.getMyNodeInfo()
        interface.close()

        if my_info and my_info.get("user"):
            node_id = my_info["user"].get("id", "unknown")
            return node_id if node_id.startswith("!") else "!" + node_id
    except Exception as e:
        print(f"Warning: Could not get node ID for {port}: {e}")
    return "unknown"


def run_gateway_thread(
    config: BridgeConfig, transport: MeshtasticTransport, stop_event: threading.Event
) -> None:
    """Run the gateway in a separate thread."""
    try:
        print("\n" + "=" * 60)
        print("GATEWAY MODE (COM9) - Starting...")
        print("=" * 60)

        from atlas_meshtastic_bridge.gateway import MeshtasticGateway

        gateway = MeshtasticGateway(
            transport,
            api_base_url=config.api_base_url,
            token=config.api_token,
        )

        print("[GATEWAY] Listening for requests...")
        print(f"[GATEWAY] API URL: {config.api_base_url}")
        print("[GATEWAY] Note: API errors are expected if URL is not accessible")

        # Run gateway with polling, checking stop event
        while not stop_event.is_set():
            try:
                gateway.run_once(timeout=0.5)
            except Exception as e:
                # Log but continue - API errors don't stop the gateway
                LOGGER.debug("Gateway processing error (non-fatal): %s", e)
            time.sleep(0.1)

        print("\n[GATEWAY] Stopping...")
        gateway.stop()
    except KeyboardInterrupt:
        print("\n[GATEWAY] Interrupted")
    except Exception as e:
        print(f"\n[GATEWAY ERROR] {e}")
        import traceback

        traceback.print_exc()


def main():
    print("=" * 60)
    print("Atlas Meshtastic Bridge Integration Test")
    print("=" * 60)
    print("\nThis test uses:")
    print("  - COM8: Client (sends API requests)")
    print("  - COM9: Gateway (receives, processes, responds)")
    print("=" * 60)

    # Get node IDs
    print("\n[1/3] Getting node IDs...")
    com8_node_id = get_node_id("COM8")
    com9_node_id = get_node_id("COM9")
    print(f"      COM8 (Client) Node ID: {com8_node_id}")
    print(f"      COM9 (Gateway) Node ID: {com9_node_id}")

    if com8_node_id == "unknown" or com9_node_id == "unknown":
        print("\n[ERROR] Could not get node IDs. Make sure both radios are connected.")
        return

    # Gateway configuration (COM9)
    print("\n[2/3] Setting up gateway (COM9)...")
    # API URL for testing
    api_url = "http://localhost:8000"  # Atlas Command API base URL

    gateway_config = BridgeConfig(
        mode="gateway",
        gateway_node_id=com9_node_id,  # Gateway's own node ID
        api_base_url=api_url,
        api_token=None,  # Add token if needed
        simulate_radio=False,
        timeout=30.0,
    )
    gateway_config._radio_port = "COM9"
    gateway_config._node_id = "gateway"

    gateway_radio = build_radio(False, "COM9", "gateway")
    gateway_transport = MeshtasticTransport(gateway_radio, segment_size=60)

    # Client configuration (COM8)
    print("\n[3/3] Setting up client (COM8)...")
    client_config = BridgeConfig(
        mode="client",
        gateway_node_id=com9_node_id,  # Send to gateway
        api_base_url=api_url,  # Not used by client, but kept for consistency
        api_token=None,
        simulate_radio=False,
        timeout=30.0,
    )
    client_config._command = "list_entities"
    client_config._data = '{"limit":5}'
    client_config._radio_port = "COM8"
    client_config._node_id = "client"

    client_radio = build_radio(False, "COM8", "client")
    client_transport = MeshtasticTransport(client_radio, segment_size=60)

    # Start gateway in a separate thread
    print("\n" + "=" * 60)
    print("Starting gateway in background thread...")
    print("=" * 60)
    stop_event = threading.Event()
    gateway_thread = threading.Thread(
        target=run_gateway_thread,
        args=(gateway_config, gateway_transport, stop_event),
        daemon=True,
    )
    gateway_thread.start()

    # Give gateway time to start
    print("\nWaiting 5 seconds for gateway to initialize...")
    time.sleep(5)

    # Run client test
    print("\n" + "=" * 60)
    print("CLIENT MODE (COM8) - Sending request...")
    print("=" * 60)
    print(f"Command: {client_config._command}")
    print(f"Data: {client_config._data}")
    print(f"Gateway: {com9_node_id}")
    print("=" * 60 + "\n")

    try:
        print("Sending request and waiting for response...\n")
        response = None

        # Call client manually to get response object
        from atlas_meshtastic_bridge.client import MeshtasticClient

        command = client_config._command
        data_str = client_config._data
        payload = json.loads(data_str)
        client = MeshtasticClient(client_transport, client_config.gateway_node_id)

        # Enable debug logging to see what's happening
        logging.getLogger("atlas_meshtastic_bridge").setLevel(logging.DEBUG)

        response = client.send_request(command, payload, timeout=client_config.timeout)

        print("\n" + "=" * 60)
        print("[SUCCESS] Bridge communication worked!")
        print("  [OK] Client sent request")
        print("  [OK] Gateway received request")
        print("  [OK] Gateway sent response")
        print("  [OK] Client received response")
        print("\nResponse:")
        print(json.dumps(response.to_dict(), indent=2))

        if response.type == "error":
            print("\n[NOTE] Gateway returned an error response.")
            print("       This is expected if the API URL is not accessible.")
            print("       The bridge communication itself worked correctly!")
        elif response.type == "response":
            print("\n[SUCCESS] Gateway successfully called API and returned data!")
            if response.data and "result" in response.data:
                result = response.data["result"]
                print(f"\nAPI returned {len(result) if isinstance(result, list) else 'data'}")
        print("=" * 60)
    except TimeoutError as e:
        print("\n" + "=" * 60)
        print("[TIMEOUT] No response received")
        print(f"  Error: {e}")
        print("  This could mean:")
        print("    - Gateway didn't receive the request")
        print("    - Gateway received but couldn't process it")
        print("    - Response got lost in transmission")
        print("=" * 60)
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"[ERROR] {e}")
        print("=" * 60)
        import traceback

        traceback.print_exc()

    # Keep running for a bit to see any delayed messages
    print("\n" + "=" * 60)
    print("Monitoring for 10 more seconds...")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    try:
        time.sleep(10)
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    finally:
        # Stop gateway thread
        print("\nStopping gateway...")
        stop_event.set()
        gateway_thread.join(timeout=2)

    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
