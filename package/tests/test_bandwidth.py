"""Bandwidth test for Atlas Meshtastic bridge.

Measures throughput (kbps) by sending progressively larger payloads
and measuring round-trip time.
"""

from __future__ import annotations

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
from atlas_meshtastic_bridge.gateway import MeshtasticGateway
from atlas_meshtastic_bridge.transport import MeshtasticTransport

logging.basicConfig(
    level=logging.INFO,  # Show info level for debugging bandwidth issues
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s",
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
        LOGGER.info("[GATEWAY] Starting gateway thread")
        gateway = MeshtasticGateway(
            transport,
            api_base_url=config.api_base_url,
            token=config.api_token,
        )

        poll_count = 0
        # Run gateway with polling, checking stop event
        # Balance between responsiveness and CPU usage
        while not stop_event.is_set():
            try:
                poll_count += 1
                if poll_count % 20 == 0:  # Log every 20 polls (~10 seconds)
                    LOGGER.info("[GATEWAY] Polling for messages... (poll #%d)", poll_count)
                gateway.run_once(timeout=0.5)  # Check for messages every 0.5 seconds
            except Exception as e:
                LOGGER.warning("[GATEWAY] Processing error (non-fatal): %s", e)
            time.sleep(0.05)  # Small sleep to prevent CPU spinning

        LOGGER.info("[GATEWAY] Stopping gateway thread")
        gateway.stop()
    except Exception as e:
        LOGGER.error(f"[GATEWAY] Gateway error: {e}", exc_info=True)


def create_test_payload(size_bytes: int) -> dict:
    """Create a test payload of specified size."""
    # Create a payload with enough data to reach target size
    # Each character is ~1 byte, so we need size_bytes characters
    data = {
        "test_data": "x" * max(0, size_bytes - 100),  # Reserve 100 bytes for JSON overhead
        "timestamp": time.time(),
        "size": size_bytes,
    }
    return data


def main():
    print("=" * 70)
    print("Atlas Meshtastic Bridge Bandwidth Test")
    print("=" * 70)
    print("\nThis test measures throughput (kbps) by sending progressively")
    print("larger payloads and measuring round-trip time.")
    print("=" * 70)

    # Set maximum test duration (10 minutes - should be much faster with optimizations)
    MAX_TEST_DURATION = 10 * 60  # 10 minutes
    test_start_time = time.time()

    # Get node IDs (optional - ports may be locked by other processes)
    print("\n[1/4] Getting node IDs...")
    com8_node_id = get_node_id("COM8")
    com9_node_id = get_node_id("COM9")
    print(f"      COM8 (Client) Node ID: {com8_node_id}")
    print(f"      COM9 (Gateway) Node ID: {com9_node_id}")

    if com8_node_id == "unknown" or com9_node_id == "unknown":
        print("\n[WARNING] Could not get node IDs (ports may be locked).")
        print("          This is OK - node IDs will be retrieved when radios are opened.")
        print("          If you see 'PermissionError' or 'Access is denied', close:")
        print("            - Meshtastic app (if running)")
        print("            - Other Python scripts using COM8/COM9")
        print("            - Any serial terminal programs")
        print("          Then try again.\n")
        # Use placeholder - will be updated when radios are opened
        com8_node_id = "!db583ef4"  # Will be updated from actual radio
        com9_node_id = "!9e9f370c"  # Will be updated from actual radio

    # Setup gateway
    print("\n[2/4] Setting up gateway (COM9)...")
    api_url = "http://localhost:8000"

    gateway_config = BridgeConfig(
        mode="gateway",
        gateway_node_id=com9_node_id,
        api_base_url=api_url,
        api_token=None,
        simulate_radio=False,
        timeout=30.0,
    )
    gateway_config._radio_port = "COM9"  # type: ignore[attr-defined]
    gateway_config._node_id = "gateway"  # type: ignore[attr-defined]

    gateway_radio = build_radio(False, "COM9", "gateway")
    gateway_transport = MeshtasticTransport(gateway_radio, segment_size=60)

    # Get actual node IDs from opened radios if we couldn't get them before
    if com9_node_id.startswith("!") and com9_node_id != "!unknown":
        try:
            if hasattr(gateway_radio, "_interface"):
                interface = getattr(gateway_radio, "_interface", None)  # type: ignore[attr-defined]
                if interface:
                    my_info = interface.getMyNodeInfo()
                    if my_info and my_info.get("user"):
                        com9_node_id = my_info["user"].get("id", com9_node_id)
                        if not com9_node_id.startswith("!"):
                            com9_node_id = "!" + com9_node_id
                        print(f"      Retrieved Gateway Node ID: {com9_node_id}")
        except Exception:  # noqa: S110
            pass

    # Setup client
    print("\n[3/4] Setting up client (COM8)...")
    client_config = BridgeConfig(
        mode="client",
        gateway_node_id=com9_node_id,
        api_base_url=api_url,
        api_token=None,
        simulate_radio=False,
        timeout=30.0,
    )
    client_config._radio_port = "COM8"  # type: ignore[attr-defined]
    client_config._node_id = "client"  # type: ignore[attr-defined]

    client_radio = build_radio(False, "COM8", "client")
    client_transport = MeshtasticTransport(client_radio, segment_size=60)

    # Get actual node IDs from opened radios if we couldn't get them before
    if com8_node_id.startswith("!") and com8_node_id != "!unknown":
        try:
            if hasattr(client_radio, "_interface"):
                interface = getattr(client_radio, "_interface", None)  # type: ignore[attr-defined]
                if interface:
                    my_info = interface.getMyNodeInfo()
                    if my_info and my_info.get("user"):
                        com8_node_id = my_info["user"].get("id", com8_node_id)
                        if not com8_node_id.startswith("!"):
                            com8_node_id = "!" + com8_node_id
                        print(f"      Retrieved Client Node ID: {com8_node_id}")
        except Exception:  # noqa: S110
            pass

    # Start gateway
    print("\n[4/4] Starting gateway in background thread...")
    stop_event = threading.Event()
    gateway_thread = threading.Thread(
        target=run_gateway_thread,
        args=(gateway_config, gateway_transport, stop_event),
        daemon=True,
    )
    gateway_thread.start()

    # Wait for gateway to initialize
    print("Waiting 5 seconds for gateway to initialize...")
    time.sleep(5)

    # Test different payload sizes
    print("\n" + "=" * 70)
    print("Running Bandwidth Tests")
    print("=" * 70)

    # Note: We need to add an "echo" command to the gateway for this test
    # For now, we'll use a command that returns data
    # Actually, let's create a simple echo handler in the gateway for testing

    # Optimized test sizes - compression + larger segments = fewer chunks
    test_sizes = [
        50,  # ~50 bytes (should compress to 1 chunk)
        100,  # ~100 bytes (1-2 chunks)
        200,  # ~200 bytes (1-2 chunks)
        500,  # ~500 bytes (2-3 chunks with compression)
        1000,  # ~1 KB (3-4 chunks with compression)
    ]

    results = []

    for size_bytes in test_sizes:
        # Check if we've exceeded maximum test duration
        elapsed_time = time.time() - test_start_time
        if elapsed_time >= MAX_TEST_DURATION:
            print(
                f"\n[WARNING] Maximum test duration ({MAX_TEST_DURATION/60:.1f} minutes) exceeded."
            )
            print(f"          Stopping test early. Elapsed: {elapsed_time/60:.1f} minutes")
            break

        print(f"\nTesting {size_bytes} bytes payload ({size_bytes/1024:.2f} KB):")
        print(
            f"Test elapsed time: {elapsed_time/60:.1f} minutes / {MAX_TEST_DURATION/60:.1f} minutes"
        )
        print("-" * 70)

        # For now, we'll use a simple test that sends data and gets it back
        # We need to modify the gateway to have an echo command
        # Let's use list_entities with a small limit as a proxy test
        # Actually, better: let's create a test command that echoes back the data

        try:
            from atlas_meshtastic_bridge.client import MeshtasticClient

            client = MeshtasticClient(client_transport, com9_node_id)

            # Create test payload
            test_data = create_test_payload(size_bytes)

            # Measure round-trip time using the echo command
            times = []
            successes = 0

            for i in range(3):
                # Check timeout before each iteration
                elapsed_time = time.time() - test_start_time
                if elapsed_time >= MAX_TEST_DURATION:
                    print(
                        f"\n[WARNING] Maximum test duration exceeded. Stopping at iteration {i+1}/3"
                    )
                    LOGGER.warning("[TEST] Maximum test duration exceeded, stopping early")
                    break

                iteration_start = time.time()
                try:
                    # Add delay between iterations to avoid overwhelming the gateway
                    # Also allows time for any retries/ACKs to complete
                    if i > 0:
                        wait_start = time.time()
                        LOGGER.info("[TEST] Waiting 2s before iteration %d...", i + 1)
                        time.sleep(2.0)  # Longer delay to ensure previous message fully processed
                        LOGGER.info(
                            "[TEST] Waited %.3fs, starting iteration %d",
                            time.time() - wait_start,
                            i + 1,
                        )
                        iteration_start = time.time()  # Reset after delay

                    LOGGER.info(
                        "[TEST] Starting iteration %d/%d for %d bytes payload",
                        i + 1,
                        3,
                        size_bytes,
                    )
                    print(f"  Sending iteration {i+1}...", end=" ", flush=True)

                    send_start = time.time()
                    LOGGER.info("[CLIENT] Sending test_echo request (ID will be generated)")
                    response = client.send_request(
                        "test_echo", test_data, timeout=90.0, max_retries=1
                    )  # Longer timeout, fewer retries
                    send_end = time.time()

                    elapsed = send_end - send_start
                    total_elapsed = send_end - iteration_start

                    LOGGER.info(
                        "[CLIENT] Received response in %.3fs (total iteration time: %.3fs)",
                        elapsed,
                        total_elapsed,
                    )
                    print("Received", flush=True)

                    # Verify response
                    if (
                        response.type == "response"
                        and response.data
                        and response.data.get("result")
                    ):
                        times.append(elapsed)
                        successes += 1
                        print(f"  Iteration {i+1}: {elapsed:.3f}s")
                        LOGGER.info("[TEST] Iteration %d succeeded: %.3fs", i + 1, elapsed)
                    else:
                        print(f"  Iteration {i+1}: Failed (wrong response type)")
                        LOGGER.warning(
                            "[TEST] Iteration %d failed: response type=%s",
                            i + 1,
                            response.type,
                        )

                except Exception as e:
                    elapsed_time = time.time() - iteration_start
                    print(f"  Iteration {i+1}: Failed ({e})")
                    LOGGER.error(
                        "[TEST] Iteration %d failed after %.3fs: %s",
                        i + 1,
                        elapsed_time,
                        e,
                        exc_info=True,
                    )

            if times:
                avg_time = sum(times) / len(times)
                # Calculate bandwidth: (payload_size_bytes * 8 bits) / avg_time_seconds / 1000 = kbps
                # Multiply by 2 for round-trip (request + response)
                total_bits = size_bytes * 8 * 2
                avg_kbps = (total_bits / avg_time) / 1000.0
                success_rate = successes / 3.0

                results.append(
                    {
                        "size_bytes": size_bytes,
                        "size_kb": size_bytes / 1024.0,
                        "avg_time": avg_time,
                        "kbps": avg_kbps,
                        "success_rate": success_rate,
                    }
                )

                print(f"\n  Average: {avg_time:.3f}s")
                print(f"  Bandwidth: {avg_kbps:.2f} kbps")
                print(f"  Success rate: {success_rate*100:.1f}%")
            else:
                print("\n  Failed: No successful iterations")
                results.append(
                    {
                        "size_bytes": size_bytes,
                        "size_kb": size_bytes / 1024.0,
                        "avg_time": 0.0,
                        "kbps": 0.0,
                        "success_rate": 0.0,
                    }
                )

        except Exception as e:
            print(f"  Error: {e}")
            import traceback

            traceback.print_exc()

    # Print summary
    total_test_time = time.time() - test_start_time
    print("\n" + "=" * 70)
    print("Bandwidth Test Summary")
    print(f"Total test duration: {total_test_time/60:.1f} minutes")
    print("=" * 70)
    print(f"{'Size':<12} {'Time (s)':<12} {'Bandwidth (kbps)':<18} {'Success Rate':<12}")
    print("-" * 70)

    for result in results:
        print(
            f"{result['size_kb']:>6.2f} KB    {result['avg_time']:>10.3f}    {result['kbps']:>15.2f}         {result['success_rate']*100:>9.1f}%"
        )

    if results:
        avg_kbps = sum(r["kbps"] for r in results if r["kbps"] > 0) / len(
            [r for r in results if r["kbps"] > 0]
        )
        print("-" * 70)
        print(f"Average Bandwidth: {avg_kbps:.2f} kbps")

    print("=" * 70)

    # Cleanup
    print("\n--- Cleanup ---")

    # Stop gateway thread
    print("Stopping gateway thread...")
    stop_event.set()
    if gateway_thread.is_alive():
        gateway_thread.join(timeout=2)

    # Close radios
    print("Closing radio interfaces...")
    if hasattr(client_radio, "close"):
        try:
            client_radio.close()
            print("  Client radio (COM8) closed")
        except Exception as e:
            print(f"  Error closing client radio: {e}")

    if hasattr(gateway_radio, "close"):
        try:
            gateway_radio.close()
            print("  Gateway radio (COM9) closed")
        except Exception as e:
            print(f"  Error closing gateway radio: {e}")

    print("Test complete!")


if __name__ == "__main__":
    main()
