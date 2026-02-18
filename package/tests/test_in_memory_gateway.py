from __future__ import annotations

import asyncio
import threading

from atlas_meshtastic_bridge.client import MeshtasticClient
from atlas_meshtastic_bridge.gateway import MeshtasticGateway
from atlas_meshtastic_bridge.transport import (
    InMemoryRadio,
    InMemoryRadioBus,
    MeshtasticTransport,
)


class DummyGateway(MeshtasticGateway):
    """Gateway variant that runs operations without the HTTP client/event loop."""

    def _ensure_event_loop(
        self,
    ) -> None:  # pragma: no cover - intentionally overrides base
        return

    def _cleanup_event_loop(self) -> None:  # pragma: no cover - no loop to clean up
        return

    def _run_operation(self, module, data, envelope):
        async def _inner():
            return await module.run(None, envelope, data)

        return asyncio.run(_inner())


def test_client_gateway_round_trip_with_in_memory_radio() -> None:
    bus = InMemoryRadioBus()
    gateway_transport = MeshtasticTransport(InMemoryRadio("gateway", bus))
    client_transport = MeshtasticTransport(InMemoryRadio("client", bus))

    gateway = DummyGateway(
        gateway_transport,
        api_base_url="http://unused",
        command_map={"test_echo": "_echo"},
    )

    gateway_thread = threading.Thread(
        target=gateway.run_forever, kwargs={"poll_interval": 0.05}, daemon=True
    )
    gateway_thread.start()

    client = MeshtasticClient(client_transport, gateway_node_id="gateway")
    try:
        response = client.send_request(
            "test_echo",
            {"message": "hello-mesh"},
            timeout=3.0,
            max_retries=0,
        )
    finally:
        gateway.stop()
        gateway_thread.join(timeout=2.0)

    assert response is not None
    assert response.type == "response"
    assert response.data and response.data.get("result", {}).get("echo") == {
        "message": "hello-mesh"
    }
