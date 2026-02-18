"""Test Meshtastic bridge performance across different modem presets.

This script tests bandwidth with different Meshtastic modem configurations:
- LONG_FAST (default) - Long range, faster
- LONG_SLOW - Long range, maximum reliability
- LONG_MODERATE - Long range, balanced
- VERY_LONG_SLOW - Maximum range, very slow
- SHORT_FAST - Short range, fast
- SHORT_SLOW - Short range, reliable
- SHORT_TURBO - Short range, maximum speed (for close proximity)
- MEDIUM_FAST - Medium range, fast
- MEDIUM_SLOW - Medium range, reliable

Each mode has different data rates and characteristics.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

# Add parent directory to path for imports
# Add connection_packages to path for atlas_meshtastic_bridge imports
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

import pytest

# Skip this entire module if meshtastic is not available
pytest.importorskip("meshtastic")

from atlas_meshtastic_bridge.cli import SerialRadioAdapter
from atlas_meshtastic_bridge.client import MeshtasticClient
from atlas_meshtastic_bridge.gateway import DEFAULT_COMMAND_MAP, MeshtasticGateway
from atlas_meshtastic_bridge.transport import MeshtasticTransport
from meshtastic import config_pb2, serial_interface

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Modem presets to test - maps name to config_pb2 enum value
MODEM_PRESETS = [
    ("LONG_FAST", config_pb2.Config.LoRaConfig.ModemPreset.LONG_FAST),
    ("LONG_SLOW", config_pb2.Config.LoRaConfig.ModemPreset.LONG_SLOW),
    ("LONG_MODERATE", config_pb2.Config.LoRaConfig.ModemPreset.LONG_MODERATE),
    ("VERY_LONG_SLOW", config_pb2.Config.LoRaConfig.ModemPreset.VERY_LONG_SLOW),
    ("SHORT_FAST", config_pb2.Config.LoRaConfig.ModemPreset.SHORT_FAST),
    ("SHORT_SLOW", config_pb2.Config.LoRaConfig.ModemPreset.SHORT_SLOW),
    ("SHORT_TURBO", config_pb2.Config.LoRaConfig.ModemPreset.SHORT_TURBO),
    ("MEDIUM_FAST", config_pb2.Config.LoRaConfig.ModemPreset.MEDIUM_FAST),
    ("MEDIUM_SLOW", config_pb2.Config.LoRaConfig.ModemPreset.MEDIUM_SLOW),
]

# Theoretical data rates (bps) for reference
MODEM_DATA_RATES = {
    "LONG_FAST": 1600,
    "LONG_SLOW": 150,
    "LONG_MODERATE": 400,
    "VERY_LONG_SLOW": 30,
    "SHORT_FAST": 10940,
    "SHORT_SLOW": 6250,
    "SHORT_TURBO": 21880,
    "MEDIUM_FAST": 4300,
    "MEDIUM_SLOW": 1000,
}


@dataclass
class ModeTestResult:
    mode_name: str
    success: bool
    round_trip_time: float
    payload_size: int
    bandwidth_kbps: float
    error: Optional[str] = None


def get_interface(port: str) -> serial_interface.SerialInterface:
    """Open a serial interface to a Meshtastic radio."""
    return serial_interface.SerialInterface(port)


def get_current_modem_preset(interface: serial_interface.SerialInterface) -> int:
    """Get the current modem preset from a radio."""
    try:
        config = interface.localNode.localConfig
        return config.lora.modem_preset
    except Exception as e:
        logger.warning(f"Could not get current modem preset: {e}")
        return config_pb2.Config.LoRaConfig.ModemPreset.LONG_FAST


def set_modem_preset(
    interface: serial_interface.SerialInterface, preset: int, preset_name: str
) -> bool:
    """Set the modem preset on a radio. Returns True if successful."""
    try:
        logger.info(f"Setting modem preset to {preset_name}...")

        # Get current config
        config = interface.localNode.localConfig

        # Set new preset
        config.lora.modem_preset = preset

        # Write config back
        interface.localNode.writeConfig("lora")

        # Wait for radio to apply changes
        logger.info(f"Waiting for radio to apply {preset_name} settings...")
        time.sleep(3)  # Give radio time to reconfigure

        return True
    except Exception as e:
        logger.error(f"Failed to set modem preset: {e}")
        return False


def run_single_test(
    client: MeshtasticClient,
    gateway: MeshtasticGateway,
    stop_event: threading.Event,
    payload_size: int = 100,
    timeout: float = 120.0,
) -> Tuple[bool, float, Optional[str]]:
    """Run a single request/response test. Returns (success, time, error)."""

    # Create test data
    test_data = {"echo_data": "X" * payload_size, "timestamp": time.time()}

    # Start gateway polling in background
    gateway_thread = threading.Thread(
        target=run_gateway_thread,
        args=(gateway, stop_event),
        daemon=True,
    )
    gateway_thread.start()

    # Give gateway time to start
    time.sleep(1)

    start_time = time.time()
    try:
        client.send_request("test_echo", test_data, timeout=timeout, max_retries=1)
        elapsed = time.time() - start_time
        return True, elapsed, None
    except TimeoutError as e:
        elapsed = time.time() - start_time
        return False, elapsed, str(e)
    except Exception as e:
        elapsed = time.time() - start_time
        return False, elapsed, str(e)
    finally:
        stop_event.set()
        gateway_thread.join(timeout=2)


def run_gateway_thread(
    gateway: MeshtasticGateway,
    stop_event: threading.Event,
) -> None:
    """Run gateway polling loop."""
    poll_count = 0
    while not stop_event.is_set():
        poll_count += 1
        if poll_count % 20 == 0:
            logger.info(f"[GATEWAY] Polling for messages... (poll #{poll_count})")
        gateway.run_once(timeout=0.5)
        time.sleep(0.05)


def run_mode_test(
    mode_name: str,
    mode_preset: int,
    com8_interface: serial_interface.SerialInterface,
    com9_interface: serial_interface.SerialInterface,
    payload_size: int = 100,
) -> ModeTestResult:
    """Test a single modem mode and return results."""

    print(f"\n{'='*60}")
    print(f"Testing: {mode_name}")
    print(f"Theoretical data rate: {MODEM_DATA_RATES.get(mode_name, 'unknown')} bps")
    print(f"{'='*60}")

    # Set modem preset on both radios
    logger.info(f"Configuring COM8 radio for {mode_name}...")
    if not set_modem_preset(com8_interface, mode_preset, mode_name):
        return ModeTestResult(
            mode_name=mode_name,
            success=False,
            round_trip_time=0,
            payload_size=payload_size,
            bandwidth_kbps=0,
            error="Failed to configure COM8",
        )

    logger.info(f"Configuring COM9 radio for {mode_name}...")
    if not set_modem_preset(com9_interface, mode_preset, mode_name):
        return ModeTestResult(
            mode_name=mode_name,
            success=False,
            round_trip_time=0,
            payload_size=payload_size,
            bandwidth_kbps=0,
            error="Failed to configure COM9",
        )

    # Wait extra time for radios to sync after config change
    logger.info("Waiting for radios to sync after config change...")
    time.sleep(5)

    # Close and reopen interfaces to ensure clean state
    com8_interface.close()
    com9_interface.close()
    time.sleep(2)

    com8_interface_new = None
    com9_interface_new = None
    gateway_radio = None
    client_radio = None

    try:
        # Reopen interfaces
        com8_interface_new = get_interface("COM8")
        com9_interface_new = get_interface("COM9")
        time.sleep(2)

        # Get node IDs
        com8_node = com8_interface_new.getMyNodeInfo()
        com9_node = com9_interface_new.getMyNodeInfo()
        # The user ID may already have ! prefix, so normalize it
        com8_raw_id = com8_node["user"]["id"] if com8_node else "unknown"
        com9_raw_id = com9_node["user"]["id"] if com9_node else "unknown"
        com8_node_id = com8_raw_id if com8_raw_id.startswith("!") else f"!{com8_raw_id}"
        com9_node_id = com9_raw_id if com9_raw_id.startswith("!") else f"!{com9_raw_id}"

        logger.info(f"COM8 Node ID: {com8_node_id}")
        logger.info(f"COM9 Node ID: {com9_node_id}")

        # Build radios using our adapter
        gateway_radio = SerialRadioAdapter(com9_interface_new)
        client_radio = SerialRadioAdapter(com8_interface_new)

        # Create transports
        gateway_transport = MeshtasticTransport(gateway_radio, segment_size=120)
        client_transport = MeshtasticTransport(client_radio, segment_size=120)

        # Create gateway and client
        gateway = MeshtasticGateway(
            transport=gateway_transport,
            api_base_url="http://localhost:8000",  # Not used for echo
            token=None,
            command_map=DEFAULT_COMMAND_MAP,
        )
        client = MeshtasticClient(client_transport, com9_node_id)

        # Run test
        stop_event = threading.Event()
        print(f"  Sending test payload ({payload_size} bytes)...")

        success, elapsed, error = run_single_test(client, gateway, stop_event, payload_size)

        # Calculate bandwidth
        if success and elapsed > 0:
            # Round trip = request + response, so total data = 2 * payload
            total_bytes = payload_size * 2
            bandwidth_kbps = (total_bytes * 8 / 1000) / elapsed
        else:
            bandwidth_kbps = 0

        result = ModeTestResult(
            mode_name=mode_name,
            success=success,
            round_trip_time=elapsed,
            payload_size=payload_size,
            bandwidth_kbps=bandwidth_kbps,
            error=error,
        )

        if success:
            print(f"  SUCCESS: {elapsed:.2f}s, {bandwidth_kbps:.3f} kbps")
        else:
            print(f"  FAILED: {error}")

        return result

    except Exception as e:
        logger.error(f"Error testing {mode_name}: {e}")
        return ModeTestResult(
            mode_name=mode_name,
            success=False,
            round_trip_time=0,
            payload_size=payload_size,
            bandwidth_kbps=0,
            error=str(e),
        )
    finally:
        # Clean up radios (which closes interfaces)
        if gateway_radio:
            gateway_radio.close()
        elif com9_interface_new:
            com9_interface_new.close()

        if client_radio:
            client_radio.close()
        elif com8_interface_new:
            com8_interface_new.close()


def main():
    print("=" * 70)
    print("Meshtastic Modem Mode Performance Test")
    print("=" * 70)
    print()
    print("This test compares bandwidth across different Meshtastic modem presets.")
    print("Each mode has different range/speed tradeoffs.")
    print()
    print("WARNING: This test will change your radio configuration!")
    print("         Original settings will be restored at the end.")
    print("=" * 70)

    # Open initial interfaces to get current settings
    print("\n[1/3] Opening radio interfaces...")
    try:
        com8_interface = get_interface("COM8")
        com9_interface = get_interface("COM9")
        time.sleep(2)
    except Exception as e:
        print(f"\nERROR: Could not open radio interfaces: {e}")
        print("Make sure both radios are connected and no other apps are using them.")
        return

    # Save original settings
    print("\n[2/3] Saving original modem settings...")
    original_com8_preset = get_current_modem_preset(com8_interface)
    original_com9_preset = get_current_modem_preset(com9_interface)
    print(f"  COM8 current preset: {original_com8_preset}")
    print(f"  COM9 current preset: {original_com9_preset}")

    # Test parameters
    payload_size = 100  # bytes
    results: List[ModeTestResult] = []

    print("\n[3/3] Running modem mode tests...")
    print(f"  Payload size: {payload_size} bytes")
    print(f"  Modes to test: {len(MODEM_PRESETS)}")

    # Test Each Mode
    try:
        # Test each mode
        for mode_name, mode_preset in MODEM_PRESETS:
            try:
                result = run_mode_test(
                    mode_name,
                    mode_preset,
                    com8_interface,
                    com9_interface,
                    payload_size,
                )
                results.append(result)

                # Reopen interfaces for next test
                try:
                    com8_interface = get_interface("COM8")
                    com9_interface = get_interface("COM9")
                    time.sleep(2)
                except Exception:  # noqa: S110
                    pass

            except Exception as e:
                logger.error(f"Error testing {mode_name}: {e}")
                results.append(
                    ModeTestResult(
                        mode_name=mode_name,
                        success=False,
                        round_trip_time=0,
                        payload_size=payload_size,
                        bandwidth_kbps=0,
                        error=str(e),
                    )
                )
    finally:
        # Restore original settings
        print("\n" + "=" * 70)
        print("Restoring original modem settings...")
        try:
            # Re-open if closed
            try:
                if "com8_interface" not in locals() or not com8_interface:
                    com8_interface = get_interface("COM8")
                if "com9_interface" not in locals() or not com9_interface:
                    com9_interface = get_interface("COM9")
                time.sleep(2)
            except Exception:  # noqa: S110
                pass

            if com8_interface:
                set_modem_preset(com8_interface, original_com8_preset, "original")
            if com9_interface:
                set_modem_preset(com9_interface, original_com9_preset, "original")

            if com8_interface:
                com8_interface.close()
            if com9_interface:
                com9_interface.close()
            print("  Original settings restored.")
        except Exception as e:
            print(f"  WARNING: Could not restore original settings: {e}")

    # Print results summary
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print(f"{'Mode':<20} {'Status':<10} {'Time (s)':<12} {'Bandwidth':<15} {'Theory (bps)':<12}")
    print("-" * 70)

    for result in results:
        status = "OK" if result.success else "FAIL"
        time_str = f"{result.round_trip_time:.2f}" if result.success else "-"
        bw_str = f"{result.bandwidth_kbps:.3f} kbps" if result.success else "-"
        theory = MODEM_DATA_RATES.get(result.mode_name, 0)

        print(f"{result.mode_name:<20} {status:<10} {time_str:<12} {bw_str:<15} {theory:<12}")

    print("-" * 70)

    # Find best mode
    successful = [r for r in results if r.success]
    if successful:
        best = max(successful, key=lambda r: r.bandwidth_kbps)
        fastest = min(successful, key=lambda r: r.round_trip_time)
        print(f"\nBest bandwidth: {best.mode_name} ({best.bandwidth_kbps:.3f} kbps)")
        print(f"Fastest response: {fastest.mode_name} ({fastest.round_trip_time:.2f}s)")
    else:
        print("\nNo successful tests!")

    print("\nTest complete!")


if __name__ == "__main__":
    main()
