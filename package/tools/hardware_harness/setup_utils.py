from __future__ import annotations

import logging
import os
import threading
from typing import Tuple

from atlas_meshtastic_bridge.cli import build_radio
from atlas_meshtastic_bridge.gateway import MeshtasticGateway
from atlas_meshtastic_bridge.transport import MeshtasticTransport


def build_transport(
    simulate: bool,
    port: str,
    node_id: str,
    spool_dir: str,
    spool_name: str,
    *,
    chunk_ttl_per_chunk: float,
    chunk_ttl_max: float,
    chunk_delay_threshold: int | None,
    chunk_delay_seconds: float,
    nack_max_per_seq: int,
    nack_interval: float,
) -> MeshtasticTransport:
    os.makedirs(spool_dir, exist_ok=True)
    radio = build_radio(simulate, port, node_id)
    spool_path = os.path.join(spool_dir, f"{spool_name}_spool.json")
    return MeshtasticTransport(
        radio,
        spool_path=spool_path,
        chunk_ttl_per_chunk=chunk_ttl_per_chunk,
        chunk_ttl_max=chunk_ttl_max,
        chunk_delay_threshold=chunk_delay_threshold,
        chunk_delay_seconds=chunk_delay_seconds,
        nack_max_per_seq=nack_max_per_seq,
        nack_interval=nack_interval,
    )


def start_gateway(
    api_base_url: str,
    api_token: str | None,
    transport: MeshtasticTransport,
) -> Tuple[MeshtasticGateway, threading.Thread]:
    gateway = MeshtasticGateway(transport, api_base_url=api_base_url, token=api_token)
    try:
        import atlas_asset_http_client_python  # type: ignore  # noqa: F401
    except ImportError as exc:
        logging.warning(
            "atlas_asset_http_client_python is not installed; gateway requests will fail until it "
            "is available: %s",
            exc,
        )

    thread = threading.Thread(target=gateway.run_forever, daemon=True, name="meshtastic-gateway")
    thread.start()
    return gateway, thread


def close_transport(transport: MeshtasticTransport) -> None:
    radio = transport.radio
    if hasattr(radio, "close"):
        try:
            radio.close()
        except (AttributeError, OSError, RuntimeError) as exc:
            logging.warning(
                "Cleanup: failed to close radio cleanly; if the device stays busy, "
                "unplug and reconnect it. Details: %s",
                exc,
            )
