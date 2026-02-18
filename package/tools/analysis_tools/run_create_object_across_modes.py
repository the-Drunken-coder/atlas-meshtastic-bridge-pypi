#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _bridge_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _ensure_path() -> None:
    root = _bridge_root()
    src = root / "src"
    harness = root / "tools" / "hardware_harness"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    if str(harness) not in sys.path:
        sys.path.insert(0, str(harness))


# Set up path before importing atlas_meshtastic_bridge
_ensure_path()

from atlas_meshtastic_bridge.modes import load_mode_profile

RUN_TIMEOUT_SECONDS = 180.0
# Mode profiles to test (bridge modes, not LoRa presets). Use None/"" to skip mode defaults.
MODES: List[str | None] = ["general"]
# Optional parameter sweeps applied to a single mode (or to all modes if desired).
# Keys can be top-level config keys or "transport.<key>" for transport overrides.
PARAM_SWEEP: Dict[str, List[object]] = {}
# How many times to run each mode/override combination.
RUNS_PER_MODE = 10

try:
    # When run as a script, harness path is added to sys.path above
    from config_utils import discover_ports, load_config, resolve_ports  # type: ignore
except ImportError:
    # Fallback for package-style invocation
    from atlas_meshtastic_bridge.tools.hardware_harness.config_utils import (  # type: ignore
        discover_ports,
        load_config,
        resolve_ports,
    )

try:
    from meshtastic import config_pb2, serial_interface
except ImportError:  # pragma: no cover - requires meshtastic
    sys.stderr.write("Meshtastic library is required for this script.\n")
    raise


MODEM_PRESETS: Dict[str, int] = {
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

LOG = logging.getLogger("mode_runner")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def open_interface(port: str):
    return serial_interface.SerialInterface(port)


def get_preset(iface) -> int:
    try:
        return iface.localNode.localConfig.lora.modem_preset
    except Exception as exc:  # pragma: no cover - depends on radio
        LOG.warning("Could not read preset on %s: %s", getattr(iface, "port", "?"), exc)
        return config_pb2.Config.LoRaConfig.ModemPreset.LONG_FAST


def set_preset(iface, preset: int, name: str) -> None:
    cfg = iface.localNode.localConfig
    cfg.lora.modem_preset = preset
    iface.localNode.writeConfig("lora")
    LOG.info("Set %s to %s", getattr(iface, "port", "?"), name)
    time.sleep(2.0)


def _open_first_working_pair(config: Dict[str, Any]) -> Tuple[Any, Any, str, str]:
    """Find two accessible ports and return opened interfaces plus port names."""
    # First try the configured/resolved pair
    candidate_pairs: List[Tuple[str, str]] = []
    try:
        candidate_pairs.append(resolve_ports(config))
    except Exception as exc:  # noqa: BLE001
        LOG.warning("resolve_ports failed (%s); will scan all ports", exc)

    # Then try all combinations of discovered ports
    try:
        ports = discover_ports()
        for i, gw in enumerate(ports):
            for j, cl in enumerate(ports):
                if i == j:
                    continue
                candidate_pairs.append((gw, cl))
    except Exception as exc:  # noqa: BLE001
        LOG.warning("Port discovery failed: %s", exc)

    tried: set[Tuple[str, str]] = set()
    for gw_port, cl_port in candidate_pairs:
        if (gw_port, cl_port) in tried:
            continue
        tried.add((gw_port, cl_port))
        try:
            gw_iface = open_interface(gw_port)
            cl_iface = open_interface(cl_port)
            LOG.info("Using gateway port %s and client port %s", gw_port, cl_port)
            return gw_iface, cl_iface, gw_port, cl_port
        except Exception as exc:  # noqa: BLE001
            LOG.warning("Skipping port pair (%s, %s): %s", gw_port, cl_port, exc)
            try:
                if "gw_iface" in locals():
                    gw_iface.close()
            except Exception as close_exc:  # noqa: BLE001
                LOG.debug(
                    "Error while closing gateway interface on port %s: %s",
                    gw_port,
                    close_exc,
                )
            try:
                if "cl_iface" in locals():
                    cl_iface.close()
            except Exception as close_exc:  # noqa: BLE001
                LOG.debug(
                    "Error while closing client interface on port %s: %s",
                    cl_port,
                    close_exc,
                )
            continue
    raise RuntimeError(f"No accessible port pairs found after trying: {list(tried)}")


def run_create_object_once(
    config_path: Path, reliability_method: str | None
) -> Tuple[bool, float, str]:
    """Run the create_object analysis tool once; return (success, duration, output)."""
    script = _bridge_root() / "tools" / "analysis_tools" / "run_create_object_test.py"
    start = time.time()
    env = {**os.environ}
    if reliability_method:
        env["ATLAS_RELIABILITY_METHOD"] = reliability_method
    else:
        env.pop("ATLAS_RELIABILITY_METHOD", None)
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "--config", str(config_path)],
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT_SECONDS,
            env=env,
        )
        duration = time.time() - start
        output = proc.stdout + "\n" + proc.stderr
        success = proc.returncode == 0
    except subprocess.TimeoutExpired as exc:  # type: ignore[attr-defined]
        duration = time.time() - start
        stdout_str = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr_str = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        output = f"{stdout_str}\n{stderr_str}\nTimeoutExpired after {duration:.2f}s"
        success = False
    match = re.search(r"create_object completed in ([0-9.]+)s", output)
    if match:
        try:
            duration = float(match.group(1))
        except ValueError as exc:
            LOG.debug(
                "Failed to parse create_object duration from output %r: %s",
                match.group(1),
                exc,
            )
    return success, duration, output


def main() -> None:
    root = _bridge_root()
    default_config = root / "tools" / "hardware_harness" / "config.json"
    base_config = load_config(str(default_config))
    if base_config.get("simulate"):
        LOG.error("Mode sweep requires real radios; config has simulate=true. Aborting.")
        return

    try:
        gw_iface, cl_iface, gateway_port, client_port = _open_first_working_pair(base_config)
    except Exception as exc:  # noqa: BLE001
        LOG.error("Failed to open two working radios: %s", exc)
        return
    orig_gw = get_preset(gw_iface)
    orig_cl = get_preset(cl_iface)
    try:
        gw_iface.close()
        cl_iface.close()
    except Exception as exc:  # noqa: BLE001
        LOG.warning("Failed to close radio interfaces cleanly: %s", exc)
    # Allow COM ports to fully release on Windows before subprocess uses them
    time.sleep(2.0)

    results: Dict[str, Dict[str, Any]] = {}
    runs_per_mode = RUNS_PER_MODE

    # Build override combinations
    sweep_keys = list(PARAM_SWEEP.keys())
    sweep_values = list(PARAM_SWEEP.values())
    if sweep_keys and len({len(v) for v in sweep_values}) != 1:
        LOG.warning("Sweep lists are uneven; only first len will be used per key")
    sweep_len = max((len(v) for v in sweep_values), default=1)

    def build_override(index: int) -> Dict[str, object]:
        override: Dict[str, object] = {}
        for key, vals in PARAM_SWEEP.items():
            if not vals:
                continue
            override[key] = vals[index % len(vals)]
        return override

    try:
        for mode_name in MODES:
            profile: Dict[str, Any] = {}
            modem_name: str | None = None
            mode_label = mode_name or "no-mode"

            if mode_name:
                try:
                    profile = dict(load_mode_profile(mode_name))
                    modem_name = profile.get("modem_preset")
                except Exception as exc:  # noqa: BLE001
                    LOG.warning("Failed to load mode profile %s: %s", mode_name, exc)

            for sweep_idx in range(max(1, sweep_len)):
                overrides = build_override(sweep_idx) if sweep_keys else {}

                updated_config = load_config(str(default_config), mode_override=mode_name)
                updated_config["mode"] = mode_name
                updated_config["gateway_port"] = gateway_port
                updated_config["client_port"] = client_port
                updated_config["simulate"] = False

                reliability_method: str | None = (
                    str(overrides.get("reliability_method"))
                    if overrides and overrides.get("reliability_method")
                    else None
                )
                if reliability_method is None:
                    reliability_method = profile.get("reliability_method")
                if reliability_method is not None:
                    updated_config["reliability_method"] = reliability_method

                transport_overrides: Dict[str, object] = {}
                for key, val in overrides.items():
                    if key.startswith("transport."):
                        transport_overrides[key.split(".", 1)[1]] = val
                    else:
                        updated_config[key] = val
                if transport_overrides:
                    updated_config["transport_overrides"] = transport_overrides

                label = mode_label
                if overrides:
                    pretty = ", ".join(f"{k}={v}" for k, v in overrides.items())
                    label = f"{mode_label} ({pretty})"

                LOG.info("=== Testing mode %s ===", label)
                temp_config_path: Path | None = None
                try:
                    # Add modem_preset to config so child process can set it
                    # (child handles preset setting to avoid serial port contention)
                    if modem_name:
                        updated_config["modem_preset"] = modem_name

                    with tempfile.NamedTemporaryFile(
                        mode="w", delete=False, suffix=".json", encoding="utf-8"
                    ) as tf:
                        json.dump(updated_config, tf)
                        temp_config_path = Path(tf.name)

                    mode_runs: List[Dict[str, Any]] = []
                    for idx in range(runs_per_mode):
                        success, duration, output = run_create_object_once(
                            temp_config_path, reliability_method
                        )
                        mode_runs.append(
                            {
                                "run": idx + 1,
                                "success": success,
                                "duration_seconds": duration,
                            }
                        )
                        LOG.info(
                            "Mode %s run %d: success=%s duration=%.2fs",
                            label,
                            idx + 1,
                            success,
                            duration,
                        )
                        if not success:
                            LOG.warning(
                                "Mode %s run %d failed. Output:\n%s",
                                label,
                                idx + 1,
                                output.strip(),
                            )
                        time.sleep(2.0)

                    successful_runs = [r for r in mode_runs if r["success"]]
                    avg = sum(float(r["duration_seconds"]) for r in successful_runs) / max(
                        1, len(successful_runs)
                    )
                    results[label] = {
                        "success": any(r["success"] for r in mode_runs),
                        "average_duration_seconds": avg,
                        "runs": mode_runs,
                    }
                finally:
                    if temp_config_path and temp_config_path.exists():
                        try:
                            temp_config_path.unlink()
                        except Exception as exc:  # noqa: BLE001
                            LOG.debug(
                                "Failed to remove temporary config file %s: %s",
                                temp_config_path,
                                exc,
                            )
    finally:
        # Restore presets
        try:
            gw_iface = open_interface(gateway_port)
            cl_iface = open_interface(client_port)
            set_preset(gw_iface, orig_gw, "original")
            set_preset(cl_iface, orig_cl, "original")
        except Exception as exc:
            LOG.warning("Failed to restore presets: %s", exc)
        try:
            gw_iface.close()
        except Exception as exc:  # noqa: BLE001
            LOG.debug("Failed to close gateway interface during cleanup: %s", exc)
        try:
            cl_iface.close()
        except Exception as exc:  # noqa: BLE001
            LOG.debug("Failed to close client interface during cleanup: %s", exc)

    # Write results
    out_path = root / "tools" / "analysis_tools" / "create_object_mode_results.txt"
    timestamp = datetime.utcnow().isoformat() + "Z"
    lines: List[str] = [f"Meshtastic create_object mode sweep @ {timestamp}", ""]
    for name, data in results.items():
        lines.append(
            f"[{name}] success={data['success']} avg_duration={data.get('average_duration_seconds', 0):.2f}s"
        )
        runs = data.get("runs", [])
        for run in runs:
            lines.append(
                f"  run {run['run']}: success={run['success']} duration={run['duration_seconds']:.2f}s"
            )
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    LOG.info("Wrote results to %s", out_path)


if __name__ == "__main__":
    main()
