#!/usr/bin/env python3
"""
Single-radio harness for Meshtastic client operations.

Finds an available Meshtastic radio (or uses a provided port), reads its node ID,
and sends preset client commands to a specified gateway node ID.

Configuration can be supplied via config.json in this directory; CLI args override.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Wire up local source paths for editable use
_HERE = Path(__file__).resolve()
# .../atlas_meshtastic_bridge/tools/analysis_tools/single_radio_harness/harness.py
# Module root is parents[3] (atlas_meshtastic_bridge); src lives directly under it.
BRIDGE_SRC = _HERE.parents[3] / "src"
if str(BRIDGE_SRC) not in sys.path:
    sys.path.insert(0, str(BRIDGE_SRC))

from atlas_meshtastic_bridge.cli import build_radio, configure_logging  # noqa: E402
from atlas_meshtastic_bridge.client import MeshtasticClient  # noqa: E402
from atlas_meshtastic_bridge.modes import load_mode_profile  # noqa: E402
from atlas_meshtastic_bridge.reliability import strategy_from_name  # noqa: E402
from atlas_meshtastic_bridge.transport import MeshtasticTransport  # noqa: E402

try:
    from meshtastic import util as meshtastic_util  # type: ignore
except Exception:
    meshtastic_util = None  # type: ignore

try:
    from serial.tools import list_ports  # type: ignore
except Exception:
    list_ports = None  # type: ignore

LOG = logging.getLogger("single_radio_harness")

PRESET_COMMANDS: Dict[str, Dict[str, Any]] = {
    "test_echo": {"data": {"message": "hello from single radio"}},
    "list_entities": {"data": {"limit": 5, "offset": 0}},
    "list_tasks": {"data": {"limit": 5}},
    "get_changed_since": {"data": {"since": "2026-01-01T00:00:00Z", "limit_per_type": 5}},
}


def load_config() -> Dict[str, Any]:
    path = _HERE.parent / "config.json"
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except Exception as exc:
        LOG.warning("Failed to load config at %s: %s", path, exc)
        return {}


def _candidate_ports() -> List[str]:
    seen: List[str] = []
    if meshtastic_util:
        try:
            ports = meshtastic_util.findPorts() or []
            for p in ports:
                if isinstance(p, dict) and "device" in p:
                    seen.append(str(p["device"]))
                else:
                    seen.append(str(p))
        except Exception as exc:  # pragma: no cover - hardware specific
            LOG.warning("Meshtastic port discovery failed: %s", exc)
    if list_ports:
        try:
            for p in list_ports.comports():
                if p.device not in seen:
                    seen.append(p.device)
        except Exception as exc:  # pragma: no cover - hardware specific
            LOG.warning("pyserial port discovery failed: %s", exc)
    return seen


def find_available_port() -> Optional[str]:
    """Return the first port we can open, skipping busy ones."""
    try:
        from meshtastic import serial_interface  # type: ignore
    except Exception:
        serial_interface = None  # type: ignore
    for port in _candidate_ports():
        if serial_interface is None:
            return port  # fall back to first discovered if we cannot test open
        try:
            iface = serial_interface.SerialInterface(port)
            iface.close()
            return port
        except Exception as exc:  # pragma: no cover - hardware specific
            LOG.warning("Port %s busy/unavailable (%s), trying next", port, exc)
            continue
    return None


def read_node_id(port: str) -> Optional[str]:
    try:
        from meshtastic import serial_interface  # type: ignore
    except Exception:
        return None
    try:
        iface = serial_interface.SerialInterface(port)
        info = getattr(iface, "getMyNodeInfo", lambda: {})() or {}
        user = info.get("user") if isinstance(info, dict) else None
        node_id = user.get("id") if isinstance(user, dict) else None
        iface.close()
        return str(node_id) if node_id else None
    except Exception as exc:  # pragma: no cover - hardware specific
        LOG.warning("Could not read node ID from %s: %s", port, exc)
        return None


def parse_args(config: Dict[str, Any]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single-radio Meshtastic client harness")
    parser.add_argument(
        "--gateway-node-id",
        default=config.get("gateway_node_id") or os.getenv("GATEWAY_NODE_ID") or "gateway",
        help="Gateway Meshtastic node ID (use !<8-hex> for hardware)",
    )
    parser.add_argument("--node-id", default=config.get("node_id"), help="Override local node ID")
    parser.add_argument("--radio-port", default=config.get("radio_port"), help="Serial port")
    parser.add_argument(
        "--simulate",
        action="store_true",
        default=bool(config.get("simulate")),
        help="Use in-memory radio",
    )
    parser.add_argument(
        "--mode",
        default=config.get("mode") or "general",
        help="Bridge mode profile name (controls reliability/transport defaults)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Override client inactivity timeout seconds (defaults to mode)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=None,
        help="Override client retries (defaults to mode)",
    )
    parser.add_argument(
        "--spool-path",
        default=config.get("spool_path", os.path.expanduser("~/.atlas_single_radio_spool.json")),
        help="Spool path",
    )
    parser.add_argument(
        "--clear-spool",
        action="store_true",
        default=bool(config.get("clear_spool", False)),
        help="Clear spool before running",
    )
    parser.add_argument("--log-level", default=config.get("log_level", "INFO"), help="Log level")
    return parser.parse_args()


def prompt_command() -> tuple[str, Dict[str, Any]]:
    keys = list(PRESET_COMMANDS.keys())
    for idx, cmd in enumerate(keys, 1):
        print(f"[{idx}] {cmd}")
    print("[c] Custom command")
    print("[q] Quit")
    choice = input("Select: ").strip().lower()
    if choice in {"q", "quit", "exit"}:
        return ("", {})
    if choice == "c":
        cmd = input("Command name: ").strip()
        data_raw = input("JSON payload (default {}): ").strip() or "{}"
        try:
            payload = json.loads(data_raw)
        except json.JSONDecodeError:
            payload = {}
        return (cmd, {"data": payload})
    try:
        index = int(choice) - 1
        cmd = keys[index]
        return (cmd, PRESET_COMMANDS[cmd])
    except Exception:
        print("Invalid selection.")
        return prompt_command()


def main() -> None:
    config = load_config()
    args = parse_args(config)
    configure_logging(args.log_level)

    # Mode profile
    profile: Dict[str, Any] = {}
    try:
        profile = dict(load_mode_profile(args.mode))
        LOG.info(
            "Loaded mode profile %s: %s",
            args.mode,
            {k: v for k, v in profile.items() if k != "transport"},
        )
    except Exception as exc:
        LOG.warning("Failed to load mode profile %s: %s (using defaults)", args.mode, exc)

    # Validate/normalize gateway node ID for hardware runs
    gw_id = args.gateway_node_id or ""
    if not args.simulate:
        cleaned = gw_id.lstrip("!")
        if not (len(cleaned) == 8 and all(c in "0123456789abcdefABCDEF" for c in cleaned)):
            LOG.error(
                "Invalid gateway-node-id '%s'. Use the radio user ID format like '!9e9f370c'.",
                gw_id,
            )
            sys.exit(1)
        gw_id = f"!{cleaned}"
    else:
        gw_id = gw_id or "gateway"

    port = args.radio_port
    if not args.simulate and not port:
        port = find_available_port()
        if not port:
            LOG.error(
                "No radio port found or available; set --radio-port explicitly and ensure it's free."
            )
            sys.exit(1)
        LOG.info("Discovered radio port: %s", port)

    node_id = args.node_id
    if not args.simulate and not node_id and port:
        node_id = read_node_id(port)
        if node_id:
            LOG.info("Using radio node ID: %s", node_id)

    mode_reliability = profile.get("reliability_method") if isinstance(profile, dict) else None
    reliability = strategy_from_name(mode_reliability)
    if mode_reliability:
        os.environ["ATLAS_RELIABILITY_METHOD"] = mode_reliability

    # Apply mode-level timeouts/retries if provided
    mode_timeout = profile.get("timeout") if isinstance(profile, dict) else None
    mode_retries = profile.get("retries") if isinstance(profile, dict) else None

    LOG.info(
        "Starting single-radio harness (port=%s, node_id=%s, gateway=%s, reliability=%s, timeout=%.1fs, retries=%d)",
        port or "simulate",
        node_id or "<auto>",
        gw_id,
        reliability.name if hasattr(reliability, "name") else mode_reliability,
        (
            mode_timeout
            if mode_timeout is not None
            else (args.timeout if args.timeout is not None else 90.0)
        ),
        (
            mode_retries
            if mode_retries is not None
            else (args.retries if args.retries is not None else 2)
        ),
    )

    radio = build_radio(args.simulate, port, node_id)
    # Transport tuning from mode profile if present
    transport_kwargs: Dict[str, Any] = {}
    if isinstance(profile, dict):
        t = profile.get("transport") or {}
        if isinstance(t, dict):
            transport_kwargs.update(t)

    transport = MeshtasticTransport(
        radio,
        spool_path=os.path.expanduser(args.spool_path),
        reliability=reliability,
        enable_spool=True,
        **transport_kwargs,
    )

    if args.clear_spool:
        try:
            if os.path.exists(os.path.expanduser(args.spool_path)):
                os.remove(os.path.expanduser(args.spool_path))
                LOG.info("Cleared spool at %s", args.spool_path)
        except Exception as exc:
            LOG.warning("Could not clear spool %s: %s", args.spool_path, exc)

    client = MeshtasticClient(transport, gateway_node_id=gw_id)

    try:
        while True:
            cmd, meta = prompt_command()
            if not cmd:
                break
            payload = meta.get("data", {})
            LOG.info("Sending %s with payload: %s", cmd, payload)
            start = time.time()
            resp = client.send_request(
                cmd,
                data=payload,
                timeout=(
                    mode_timeout
                    if mode_timeout is not None
                    else (args.timeout if args.timeout is not None else 90.0)
                ),
                max_retries=(
                    mode_retries
                    if mode_retries is not None
                    else (args.retries if args.retries is not None else 2)
                ),
            )
            elapsed = time.time() - start
            print("\n--- Response ---")
            print(json.dumps(resp.to_dict(), indent=2))
            print(f"(completed in {elapsed:.2f}s)\n")
    except KeyboardInterrupt:
        LOG.info("Interrupted; shutting down harness")
    finally:
        if hasattr(radio, "close"):
            try:
                radio.close()
            except KeyboardInterrupt:
                LOG.warning("Interrupted while closing radio; suppressing")
            except Exception as exc:
                LOG.warning("Error while closing radio: %s", exc)


if __name__ == "__main__":
    main()
