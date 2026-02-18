#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
import threading
import time
from typing import Any

# --- Quick variables: tweak defaults for ad-hoc runs ---
# Reliability strategy: none, simple, stage, window, window_fec
DEFAULT_RELIABILITY_METHOD = "window"
# Optional Meshtastic modem preset to apply to both radios (e.g., SHORT_TURBO, LONG_FAST). Use None to leave unchanged.
# This can be overridden by config["modem_preset"] or MESHTASTIC_MODE_PRESET.
DEFAULT_MODE_PRESET = None
# ------------------------------------------------------


def _ensure_package_imports() -> None:
    if __package__:
        return
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    bridge_root = os.path.abspath(os.path.join(tools_dir, "..", ".."))
    src_path = os.path.join(bridge_root, "src")
    harness_path = os.path.join(bridge_root, "tools", "hardware_harness")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    if harness_path not in sys.path:
        sys.path.insert(0, harness_path)


_ensure_package_imports()

from atlas_meshtastic_bridge.cli import configure_logging
from atlas_meshtastic_bridge.client import MeshtasticClient
from command_presets import gen_default_id, generate_realistic_content
from config_utils import (
    TRANSPORT_DEFAULTS,
    load_config,
    resolve_gateway_node_id,
    resolve_ports,
)
from setup_utils import build_transport, close_transport, start_gateway
from transport_helpers import clear_spool, retarget_spool_destination, wait_for_settled


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fire-and-forget create_object test over the dual-radio harness"
    )
    default_config = os.path.abspath(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "hardware_harness",
            "config.json",
        )
    )
    parser.add_argument(
        "--config",
        default=default_config,
        help="Path to harness config (defaults to tools/hardware_harness/config.json)",
    )
    parser.add_argument(
        "--mode",
        default=None,
        help="Bridge mode profile name to apply (blank/none disables mode defaults)",
    )
    parser.add_argument(
        "--size-kb",
        type=int,
        default=10,
        help="Payload size in KB (capped at 10 KB by the harness)",
    )
    parser.add_argument(
        "--content-type",
        default="text/plain",
        help="Content type for the generated object",
    )
    parser.add_argument(
        "--object-prefix",
        default="object",
        help="Prefix for the generated object ID",
    )
    parser.add_argument(
        "--reliability-method",
        choices=["none", "simple", "stage", "window", "window_fec"],
        default=None,
        help="Reliability strategy to use (defaults to mode/profile/config if unset)",
    )
    return parser.parse_args()


def _build_payload(size_kb: int, content_type: str, object_prefix: str) -> dict[str, Any]:
    if size_kb > 10:
        raise ValueError("Harness enforces a 10 KB limit; choose size <= 10 KB")
    object_id = gen_default_id(object_prefix)
    raw = generate_realistic_content(size_kb, content_type)
    content_b64 = base64.b64encode(raw).decode("ascii")
    file_name = f"{object_id}.txt" if content_type.startswith("text/") else f"{object_id}.bin"
    return {
        "object_id": object_id,
        "content_b64": content_b64,
        "content_type": content_type,
        "file_name": file_name,
        "usage_hint": "harness-auto",
        "size_bytes": len(raw),
    }


def main() -> None:
    args = parse_args()
    config = load_config(args.config, mode_override=args.mode)
    reliability_method = (
        args.reliability_method
        or os.getenv("ATLAS_RELIABILITY_METHOD")
        or config.get("reliability_method")
        or DEFAULT_RELIABILITY_METHOD
    )
    if reliability_method:
        os.environ["ATLAS_RELIABILITY_METHOD"] = reliability_method
    else:
        os.environ.pop("ATLAS_RELIABILITY_METHOD", None)
    mode_name = config.get("mode")
    mode_preset = (
        os.getenv("MESHTASTIC_MODE_PRESET") or config.get("modem_preset") or DEFAULT_MODE_PRESET
    )
    configure_logging(config.get("log_level", "INFO"))

    if not config.get("api_token"):
        config["api_token"] = os.getenv("ATLAS_API_TOKEN")

    logging.info(
        "Starting create_object harness run (timeout=%.1fs, retries=%s, post_response_timeout=%.1fs)",
        float(config.get("timeout", 0)),
        config.get("retries"),
        float(config.get("post_response_timeout", 0)),
    )
    if mode_name in {"", None, "none", "null"}:
        logging.info("Mode profile: none (using raw config defaults)")
    else:
        logging.info("Mode profile: %s", mode_name)
    logging.info("Using reliability method: %s", reliability_method)
    if mode_preset:
        logging.info("Requested Meshtastic modem preset: %s", mode_preset)
    else:
        logging.info("Meshtastic modem preset: leave unchanged (no override)")

    gateway_port, client_port = resolve_ports(config)
    logging.info("Using gateway port %s and client port %s", gateway_port, client_port)

    # Best-effort: set modem preset on both radios before starting transports
    if mode_preset and not config.get("simulate", False):
        try:
            from meshtastic import config_pb2, serial_interface

            preset_map = {
                "LONG_FAST": config_pb2.Config.LoRaConfig.ModemPreset.LONG_FAST,
                "LONG_SLOW": config_pb2.Config.LoRaConfig.ModemPreset.LONG_SLOW,
                "LONG_MODERATE": config_pb2.Config.LoRaConfig.ModemPreset.LONG_MODERATE,
                "VERY_LONG_SLOW": config_pb2.Config.LoRaConfig.ModemPreset.VERY_LONG_SLOW,
                "MEDIUM_FAST": config_pb2.Config.LoRaConfig.ModemPreset.MEDIUM_FAST,
                "MEDIUM_SLOW": config_pb2.Config.LoRaConfig.ModemPreset.MEDIUM_SLOW,
                "SHORT_FAST": config_pb2.Config.LoRaConfig.ModemPreset.SHORT_FAST,
                "SHORT_SLOW": config_pb2.Config.LoRaConfig.ModemPreset.SHORT_SLOW,
                "SHORT_TURBO": config_pb2.Config.LoRaConfig.ModemPreset.SHORT_TURBO,
            }
            preset_value = preset_map.get(mode_preset.upper())
            if preset_value is None:
                logging.warning("Unknown modem preset %s; skipping preset change", mode_preset)
            else:
                for name, port in (("gateway", gateway_port), ("client", client_port)):
                    try:
                        iface = serial_interface.SerialInterface(port)
                        cfg = iface.localNode.localConfig
                        cfg.lora.modem_preset = preset_value
                        iface.localNode.writeConfig("lora")
                        logging.info("Set %s radio (%s) to preset %s", name, port, mode_preset)
                        iface.close()
                        time.sleep(0.5)
                    except Exception as exc:  # noqa: BLE001
                        logging.warning(
                            "Failed to set preset %s on %s (%s): %s",
                            mode_preset,
                            name,
                            port,
                            exc,
                        )
        except ImportError as exc:  # noqa: BLE001
            logging.warning("meshtastic not available; cannot set modem preset: %s", exc)
        # Allow COM ports to fully release on Windows before building transports
        time.sleep(2.0)

    spool_dir = config.get("spool_dir") or os.path.expanduser("~/.atlas_meshtastic_spool")
    gateway_transport = build_transport(
        config.get("simulate", False),
        gateway_port,
        config.get("gateway_node_id", "gateway"),
        spool_dir,
        "gateway",
        chunk_ttl_per_chunk=float(TRANSPORT_DEFAULTS.get("chunk_ttl_per_chunk", 20.0)),
        chunk_ttl_max=float(TRANSPORT_DEFAULTS.get("chunk_ttl_max", 1800.0)),
        chunk_delay_threshold=TRANSPORT_DEFAULTS.get("chunk_delay_threshold"),
        chunk_delay_seconds=float(TRANSPORT_DEFAULTS.get("chunk_delay_seconds", 0.0)),
        nack_max_per_seq=int(TRANSPORT_DEFAULTS.get("nack_max_per_seq", 5)),
        nack_interval=float(TRANSPORT_DEFAULTS.get("nack_interval", 0.5)),
    )
    client_transport = build_transport(
        config.get("simulate", False),
        client_port,
        config.get("client_node_id", "client"),
        spool_dir,
        "client",
        chunk_ttl_per_chunk=float(TRANSPORT_DEFAULTS.get("chunk_ttl_per_chunk", 20.0)),
        chunk_ttl_max=float(TRANSPORT_DEFAULTS.get("chunk_ttl_max", 1800.0)),
        chunk_delay_threshold=TRANSPORT_DEFAULTS.get("chunk_delay_threshold"),
        chunk_delay_seconds=float(TRANSPORT_DEFAULTS.get("chunk_delay_seconds", 0.0)),
        nack_max_per_seq=int(TRANSPORT_DEFAULTS.get("nack_max_per_seq", 5)),
        nack_interval=float(TRANSPORT_DEFAULTS.get("nack_interval", 0.5)),
    )

    if config.get("clear_spool"):
        clear_spool(gateway_transport)
        clear_spool(client_transport)

    gateway_node_id = resolve_gateway_node_id(config, gateway_transport)
    logging.info("Gateway node ID: %s", gateway_node_id)
    retarget_spool_destination(client_transport, gateway_node_id)

    api_base_url = config.get("api_base_url") or "http://localhost:8000"
    gateway, gateway_thread = start_gateway(
        api_base_url=api_base_url,
        api_token=config.get("api_token"),
        transport=gateway_transport,
    )

    stop_event = threading.Event()
    client = MeshtasticClient(client_transport, gateway_node_id=gateway_node_id)

    try:
        payload = _build_payload(args.size_kb, args.content_type, args.object_prefix)
        logging.info(
            "Sending %d-byte object %s (%s)",
            payload["size_bytes"],
            payload["object_id"],
            payload["content_type"],
        )
        start = time.time()
        response = client.create_object(
            object_id=payload["object_id"],
            content_b64=payload["content_b64"],
            content_type=payload["content_type"],
            file_name=payload["file_name"],
            usage_hint=payload["usage_hint"],
            timeout=float(config.get("timeout", 30.0)),
            max_retries=int(config.get("retries", 2)),
        )
        elapsed = time.time() - start
        logging.info(
            "create_object completed in %.2fs (id=%s, response=%s)",
            elapsed,
            response.id,
            response.type,
        )
        print("\n--- Response ---")
        print(json.dumps(response.to_dict(), indent=2))

        settled = wait_for_settled(
            client_transport,
            float(config.get("post_response_quiet", 10.0)),
            float(config.get("post_response_timeout", 90.0)),
            stop_event,
        )
        if not settled:
            logging.warning("Radio did not settle before timeout; results may be in-flight")
    finally:
        stop_event.set()
        gateway.stop()
        gateway_thread.join(timeout=2.0)
        close_transport(client_transport)
        close_transport(gateway_transport)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
