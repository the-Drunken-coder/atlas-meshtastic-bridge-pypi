#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import signal
import sys
import threading
import time
from typing import TYPE_CHECKING, Any, Dict, List


def _ensure_package_imports() -> None:
    if __package__:
        return
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    bridge_root = os.path.abspath(os.path.join(tools_dir, "..", ".."))
    src_path = os.path.join(bridge_root, "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


_ensure_package_imports()

from atlas_meshtastic_bridge.cli import configure_logging
from atlas_meshtastic_bridge.client import MeshtasticClient

if TYPE_CHECKING:
    from . import command_presets as command_presets_module
    from . import config_utils as config_utils_module
    from . import diagnostics as diagnostics_module
    from . import input_utils as input_utils_module
    from . import setup_utils as setup_utils_module
    from . import transport_helpers as transport_helpers_module
else:
    try:
        from . import command_presets as command_presets_module
        from . import config_utils as config_utils_module
        from . import diagnostics as diagnostics_module
        from . import input_utils as input_utils_module
        from . import setup_utils as setup_utils_module
        from . import transport_helpers as transport_helpers_module
    except ImportError:
        import command_presets as command_presets_module  # type: ignore[import-not-found]
        import config_utils as config_utils_module  # type: ignore[import-not-found]
        import diagnostics as diagnostics_module  # type: ignore[import-not-found]
        import input_utils as input_utils_module  # type: ignore[import-not-found]
        import setup_utils as setup_utils_module  # type: ignore[import-not-found]
        import transport_helpers as transport_helpers_module  # type: ignore[import-not-found]

COMMAND_PRESETS = command_presets_module.COMMAND_PRESETS
apply_field_defaults = command_presets_module.apply_field_defaults
default_context = command_presets_module.default_context
gen_default_id = command_presets_module.gen_default_id
generate_realistic_content = command_presets_module.generate_realistic_content
run_auto_flight = command_presets_module.run_auto_flight
update_context_from_payload = command_presets_module.update_context_from_payload

TRANSPORT_DEFAULTS = config_utils_module.TRANSPORT_DEFAULTS
load_config = config_utils_module.load_config
parse_args = config_utils_module.parse_args
resolve_gateway_node_id = config_utils_module.resolve_gateway_node_id
resolve_ports = config_utils_module.resolve_ports

render_diagnostics = diagnostics_module.render_diagnostics
prompt_custom_payload = input_utils_module.prompt_custom_payload
prompt_for_payload = input_utils_module.prompt_for_payload
render_menu = input_utils_module.render_menu
build_transport = setup_utils_module.build_transport
close_transport = setup_utils_module.close_transport
start_gateway = setup_utils_module.start_gateway
ack_spool_entry = transport_helpers_module.ack_spool_entry
clear_spool = transport_helpers_module.clear_spool
retarget_spool_destination = transport_helpers_module.retarget_spool_destination
wait_for_settled = transport_helpers_module.wait_for_settled


def _apply_modem_preset(
    preset_name: str, gateway_port: str, client_port: str, simulate: bool
) -> None:
    """Best-effort apply a Meshtastic modem preset to both radios."""
    if simulate:
        logging.info("Simulation enabled; skipping modem preset change (%s)", preset_name)
        return
    try:
        from meshtastic import config_pb2, serial_interface
    except ImportError as exc:  # pragma: no cover - hardware-only path
        logging.warning(
            "meshtastic not available; cannot set modem preset %s: %s", preset_name, exc
        )
        return

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
    preset_value = preset_map.get(preset_name.upper())
    if preset_value is None:
        logging.warning("Unknown modem preset %s; skipping preset change", preset_name)
        return

    for name, port in (("gateway", gateway_port), ("client", client_port)):
        try:
            iface = serial_interface.SerialInterface(port)
            cfg = iface.localNode.localConfig
            cfg.lora.modem_preset = preset_value
            iface.localNode.writeConfig("lora")
            logging.info("Set %s radio (%s) to preset %s", name, port, preset_name)
            iface.close()
            time.sleep(0.5)
        except Exception as exc:  # pragma: no cover - hardware-only path
            logging.warning("Failed to set preset %s on %s (%s): %s", preset_name, name, port, exc)


def interactive_loop(
    client: MeshtasticClient,
    timeout: float,
    retries: int,
    quiet_window: float,
    quiet_timeout: float,
    stop_event: threading.Event,
    loop: bool,
) -> List[Dict[str, Any]]:
    actions = list(COMMAND_PRESETS.keys())
    descriptions = {cmd: meta.get("description", "") for cmd, meta in COMMAND_PRESETS.items()}
    diagnostics: List[Dict[str, Any]] = []
    context = default_context()

    def validate_field(name: str, value: Any) -> None:
        if name == "latitude":
            if not isinstance(value, (int, float)) or not (-90.0 <= value <= 90.0):
                raise ValueError("Latitude must be between -90 and 90")
        if name == "longitude":
            if not isinstance(value, (int, float)) or not (-180.0 <= value <= 180.0):
                raise ValueError("Longitude must be between -180 and 180")

    while not stop_event.is_set():
        render_menu(actions, descriptions)
        choice = input("Select an action: ").strip().lower()
        if choice in {"q", "quit", "exit"}:
            stop_event.set()
            break
        # Resolve command and prompt for payload
        if choice == "c":
            command = input("Command name: ").strip()
            if not command:
                continue
            payload = prompt_custom_payload()
        else:
            try:
                index = int(choice) - 1
                command = actions[index]
            except (ValueError, IndexError):
                print("Invalid selection.")
                continue
            fields = COMMAND_PRESETS.get(command, {}).get("fields", [])
            payload = prompt_for_payload(
                apply_field_defaults(command, fields, context),
                validator=validate_field,
            )

        run_start = time.time()
        request_bytes = len(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        response_bytes = 0
        response_type = None
        error = None
        timed_out = False
        status = "error"
        file_content_b64 = None
        try:
            # Prefer typed helpers when available for clearer field validation
            response = None
            if command == "auto_flight":
                run_auto_flight(
                    client,
                    duration_sec=int(payload.get("duration_sec", 300)),
                    steps=int(payload.get("steps", 10)),
                    context=context,
                    timeout=timeout,
                    retries=retries,
                )
                status = "success"
            elif command == "create_object":
                file_path = payload.pop("file_path", "").strip() if payload.get("file_path") else ""
                inline_content = payload.pop("content", "")
                size_kb = payload.pop("size_kb", None)
                file_name = payload.pop("file_name", "") or None
                content_type = payload.pop("content_type", "") or None
                object_type = payload.pop("type", "") or None
                object_id_val = payload.get("object_id") or gen_default_id("object")
                raw: bytes | None = None

                if file_path:
                    try:
                        with open(file_path, "rb") as fh:
                            raw = fh.read()
                    except OSError as exc:
                        raise RuntimeError(f"Failed to read file {file_path}: {exc}") from exc
                    if not file_name:
                        file_name = os.path.basename(file_path) or f"{object_id_val}.bin"
                    if not content_type:
                        guessed, _ = mimetypes.guess_type(file_path)
                        if guessed:
                            content_type = guessed
                elif inline_content:
                    raw = inline_content.encode("utf-8")
                    if not file_name:
                        file_name = f"{object_id_val}.txt"
                    if not content_type:
                        content_type = "text/plain"
                elif size_kb:
                    kb = max(1, int(size_kb))
                    raw = generate_realistic_content(kb, content_type or "text/plain")
                    if not file_name:
                        file_name = f"{object_id_val}.txt"
                    if not content_type:
                        content_type = "text/plain"
                else:
                    # Fallback to 10KB generated text if user left everything blank
                    raw = generate_realistic_content(10, content_type or "text/plain")
                    if not file_name:
                        file_name = f"{object_id_val}.txt"
                    if not content_type:
                        content_type = "text/plain"

                if raw is None:
                    raise ValueError("No content prepared for create_object")
                if not content_type:
                    raise ValueError("create_object requires 'content_type'")

                # Hard limit: block payloads larger than 10 KB until larger transfers are supported
                max_payload_bytes = 10 * 1024
                if len(raw) > max_payload_bytes:
                    status = "error"
                    error = (
                        f"Payload is {len(raw)} bytes which exceeds the 10 KB harness limit. "
                        "Large transfers are not supported yet."
                    )
                    print(f"[ERROR] {error}")
                    continue

                file_content_b64 = base64.b64encode(raw).decode("ascii")
                payload["content_b64"] = file_content_b64
                request_bytes = len(payload["content_b64"].encode("ascii"))
                if file_name:
                    payload["file_name"] = file_name
                if content_type:
                    payload["content_type"] = content_type
                if object_type:
                    payload["type"] = object_type
                # Prefer typed helper
                if hasattr(client, "create_object"):
                    response = client.create_object(**payload, timeout=timeout, max_retries=retries)
                else:
                    response = client.send_request(
                        command="create_object",
                        data=payload,
                        timeout=timeout,
                        max_retries=retries,
                    )
            elif hasattr(client, command):
                typed = getattr(client, command)
                if callable(typed):
                    try:
                        response = typed(**payload, timeout=timeout, max_retries=retries)
                    except TypeError:
                        response = typed(**payload)
                else:
                    response = client.send_request(
                        command=command,
                        data=payload,
                        timeout=timeout,
                        max_retries=retries,
                    )
            else:
                response = client.send_request(
                    command=command, data=payload, timeout=timeout, max_retries=retries
                )
            if response is not None:
                print("\n--- Response ---")
                print(json.dumps(response.to_dict(), indent=2))
                ack_spool_entry(client.transport, response.id)
                update_context_from_payload(command, payload, context)
                response_type = response.type
                response_bytes = len(
                    json.dumps(response.to_dict(), separators=(",", ":")).encode("utf-8")
                )
                status = "success" if response.type == "response" else "error"
        except TimeoutError as exc:
            timed_out = True
            error = f"{exc.__class__.__name__}: {exc}"
            print(
                f"[ERROR] Request timed out: {exc}. "
                "Potential packet loss or slow link; consider increasing timeout."
            )
        except Exception as exc:
            error = f"{exc.__class__.__name__}: {exc}"
            print(
                f"[ERROR] Request failed ({exc.__class__.__name__}): {exc}. "
                "Check radio connectivity, gateway logs, and Atlas API availability."
            )
        finally:
            duration = time.time() - run_start
            diagnostics.append(
                {
                    "command": command,
                    "status": status,
                    "duration_seconds": duration,
                    "request_bytes": request_bytes,
                    "response_bytes": response_bytes,
                    "timeout_seconds": timeout,
                    "retries": retries,
                    "response_type": response_type,
                    "error": error,
                    "timed_out": timed_out,
                }
            )
            if loop and not stop_event.is_set():
                idle = wait_for_settled(client.transport, quiet_window, quiet_timeout, stop_event)
                if not idle:
                    print(
                        "\n[WARN] Radio did not settle within the timeout; shutting down to avoid "
                        "overlapping inputs while messages are still in flight."
                    )
                    stop_event.set()
                    break
        if not loop:
            break
    return diagnostics


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    configure_logging(config.get("log_level", "INFO"))
    logging.info(
        "Resolved mode=%s reliability=%s timeout=%.1fs post_response_timeout=%.1fs retries=%s modem_preset=%s",
        config.get("mode"),
        config.get("reliability_method"),
        float(config.get("timeout", 0)),
        float(config.get("post_response_timeout", 0)),
        config.get("retries"),
        config.get("modem_preset"),
    )
    logging.info(
        (
            "Atlas Command API base URL: %s (timeout=%.1fs, retries=%s, "
            "post_response_timeout=%.1fs, 10 KB payload limit in harness)"
        ),
        config.get("api_base_url"),
        float(config.get("timeout", 0)),
        config.get("retries"),
        float(config.get("post_response_timeout", 0)),
    )
    spool_dir = str(config.get("spool_dir") or os.path.expanduser("~/.atlas_meshtastic_harness"))

    stop_event = threading.Event()

    def handle_signal(signum: int, _frame: Any) -> None:
        logging.info("Received signal %s, shutting down...", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    if not config.get("api_token"):
        config["api_token"] = os.getenv("ATLAS_API_TOKEN")

    gateway_port, client_port = resolve_ports(config)
    logging.info("Using gateway port %s and client port %s", gateway_port, client_port)

    mode_preset = os.getenv("MESHTASTIC_MODE_PRESET") or config.get("modem_preset")
    if mode_preset:
        logging.info("Requested Meshtastic modem preset: %s", mode_preset)
        _apply_modem_preset(mode_preset, gateway_port, client_port, bool(config.get("simulate")))
    else:
        logging.info("Meshtastic modem preset: leave unchanged (no override)")

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
    logging.info(
        "Starting harness with gateway port %s and client port %s (gateway node ID: %s)",
        gateway_port,
        client_port,
        gateway_node_id,
    )
    retarget_spool_destination(client_transport, gateway_node_id)

    api_base_url = str(config.get("api_base_url") or "http://localhost:8000/")
    gateway, gateway_thread = start_gateway(
        api_base_url=api_base_url,
        api_token=config.get("api_token"),
        transport=gateway_transport,
    )

    client = MeshtasticClient(client_transport, gateway_node_id=gateway_node_id)

    diagnostics: List[Dict[str, Any]] = []
    try:
        diagnostics = interactive_loop(
            client,
            timeout=float(config.get("timeout", 30.0)),
            retries=int(config.get("retries", 2)),
            quiet_window=float(config.get("post_response_quiet", 10.0)),
            quiet_timeout=float(config.get("post_response_timeout", 90.0)),
            stop_event=stop_event,
            loop=bool(config.get("loop", False)),
        )
    finally:
        stop_event.set()
        gateway.stop()
        gateway_thread.join(timeout=2.0)
        close_transport(client_transport)
        close_transport(gateway_transport)
        render_diagnostics(diagnostics)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
