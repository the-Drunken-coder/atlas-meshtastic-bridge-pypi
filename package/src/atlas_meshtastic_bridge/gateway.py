from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
from concurrent.futures import TimeoutError as FuturesTimeoutError
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Optional, Set

# Prefer the local checkout of atlas_asset_http_client_python (editable/dev) so harness
# runs catch API changes immediately. Handle both monorepo layouts:
# - connection_packages/atlas_meshtastic_bridge (sibling package under connection_packages)
# - Atlas_Client_SDKs/atlas_meshtastic_bridge (legacy layout without connection_packages)
_CANDIDATE_HTTP_CLIENT_PATHS = [
    # Sibling package in the same connection_packages folder
    Path(__file__).resolve().parents[3] / "atlas_asset_http_client_python" / "src",
    # Monorepo root -> connection_packages path (backwards compatibility)
    Path(__file__).resolve().parents[4]
    / "connection_packages"
    / "atlas_asset_http_client_python"
    / "src",
]

for _path in _CANDIDATE_HTTP_CLIENT_PATHS:
    if _path.exists():
        _path_str = str(_path)
        if _path_str not in sys.path:
            sys.path.insert(0, _path_str)
        break

try:
    from atlas_asset_http_client_python import AtlasCommandHttpClient

    _ATLAS_CLIENT_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency for tests
    _ATLAS_CLIENT_AVAILABLE = False

    class AtlasCommandHttpClient:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):  # noqa: D401
            raise ImportError(
                "atlas_asset_http_client_python is required for Meshtastic gateway operations"
            )


from .message import MessageEnvelope
from .metrics import DEFAULT_LATENCY_BUCKETS, get_metrics_registry
from .transport import MeshtasticTransport

LOGGER = logging.getLogger(__name__)


# Supported bridge operations - maps command names to API client methods
DEFAULT_COMMAND_MAP: Dict[str, str] = {
    # === Entity Operations ===
    "list_entities": "entities.list_entities",
    "get_entity": "entities.get_entity",
    "get_entity_by_alias": "entities.get_entity_by_alias",
    "create_entity": "entities.create_entity",
    "update_entity": "entities.update_entity",
    "delete_entity": "entities.delete_entity",
    "checkin_entity": "entities.checkin_entity",
    "update_telemetry": "entities.update_entity_telemetry",
    # === Task Operations ===
    "list_tasks": "tasks.list_tasks",
    "get_task": "tasks.get_task",
    "get_tasks_by_entity": "tasks.get_tasks_by_entity",
    "create_task": "tasks.create_task",
    "update_task": "tasks.update_task",
    "delete_task": "tasks.delete_task",
    "transition_task_status": "tasks.transition_task_status",
    "start_task": "tasks.start_task",
    "complete_task": "tasks.complete_task",
    "fail_task": "tasks.fail_task",
    # === Object Operations ===
    "list_objects": "objects.list_objects",
    "get_object": "objects.get_object",
    "get_objects_by_entity": "objects.get_objects_by_entity",
    "get_objects_by_task": "objects.get_objects_by_task",
    "update_object": "objects.update_object",
    "delete_object": "objects.delete_object",
    "add_object_reference": "objects.add_object_reference",
    "remove_object_reference": "objects.remove_object_reference",
    "find_orphaned_objects": "objects.find_orphaned_objects",
    "get_object_references": "objects.get_object_references",
    "validate_object_references": "objects.validate_object_references",
    "cleanup_object_references": "objects.cleanup_object_references",
    "create_object": "objects.create_object",
    # === Query Operations ===
    "get_changed_since": "get_changed_since",
    "get_full_dataset": "get_full_dataset",
    # === Test Operations ===
    "test_echo": "_echo",  # Echo back data for bandwidth testing
    # === System Operations ===
    "health_check": "health",  # Check Atlas Command health status
}


class MeshtasticGateway:
    _DEFAULT_OPERATION_TIMEOUT = 30.0
    _DEFAULT_LOOP_START_TIMEOUT = 10.0

    def __init__(
        self,
        transport: MeshtasticTransport,
        api_base_url: str,
        token: str | None = None,
        command_map: Dict[str, str] | None = None,
    ) -> None:
        self.transport = transport
        self.api_base_url = api_base_url
        self.token = token
        self.command_map = command_map or DEFAULT_COMMAND_MAP
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._client: Optional[AtlasCommandHttpClient] = None
        self._loop_lock = threading.Lock()
        self._metrics = get_metrics_registry()
        self._numeric_senders_seen: Set[str] = set()

    def run_once(self, timeout: float = 1.0) -> None:
        outbox_handler = getattr(self.transport, "process_outbox", None)
        if callable(outbox_handler):
            outbox_handler()
        receive_start = time.time()
        sender, envelope = self.transport.receive_message(timeout=timeout)
        receive_time = time.time() - receive_start

        if envelope is None or sender is None:
            if receive_time > timeout * 0.9:  # Only log if we waited most of the timeout
                LOGGER.debug("[GATEWAY] No message received after %.3fs", receive_time)
            return

        if envelope.type != "request":
            LOGGER.debug(
                "[GATEWAY] Ignoring non-request message: type=%s, id=%s",
                envelope.type,
                envelope.id[:8],
            )
            self._metrics.inc(
                "gateway_ignored_messages_total",
                labels={"reason": "non-request", "type": envelope.type or "unknown"},
            )
            return

        if not self.transport.should_process(sender, envelope):
            LOGGER.debug(
                "[GATEWAY] Duplicate request %s from %s (ignored)",
                envelope.id[:8],
                sender,
            )
            self._metrics.inc(
                "gateway_duplicate_requests_total",
                labels={"command": envelope.command or "unknown"},
            )
            return

        lease_seconds = (envelope.meta or {}).get("lease_seconds")
        dedupe_keys = self.transport.build_dedupe_keys(sender, envelope)
        in_progress_key = dedupe_keys.semantic or dedupe_keys.correlation or dedupe_keys.message
        lease_duration = lease_seconds or self.transport.deduper.lease_seconds

        if not self.transport.deduper.acquire_lease(in_progress_key, lease_seconds=lease_duration):
            LOGGER.debug(
                "[GATEWAY] Duplicate request %s for key %s already in progress",
                envelope.id[:8],
                in_progress_key,
            )
            return

        request_start = time.time()
        self._metrics.gauge("gateway_inflight_requests").inc(1)
        self._metrics.inc(
            "gateway_requests_total",
            labels={"command": envelope.command or "unknown", "status": "received"},
        )
        LOGGER.info(
            "[GATEWAY] Processing request %s from %s (received after %.3fs)",
            envelope.id[:8],
            sender,
            receive_time,
        )

        # Allow time for node discovery to complete if this is first contact
        if (
            sender
            and sender.isdigit()
            and not sender.startswith("!")
            and sender not in self._numeric_senders_seen
        ):
            LOGGER.info(
                "[GATEWAY] Sender %s is numeric ID - waiting 1.5s for node discovery",
                sender,
            )
            time.sleep(1.5)
            self._numeric_senders_seen.add(sender)

        try:
            handle_start = time.time()
            try:
                response = self._handle_request(envelope)
            except Exception as exc:
                LOGGER.exception("[GATEWAY] Unhandled error while processing %s", envelope.id[:8])
                self._metrics.inc(
                    "gateway_requests_total",
                    labels={
                        "command": envelope.command or "unknown",
                        "status": "error",
                    },
                )
                response = MessageEnvelope(
                    id=envelope.id,
                    type="error",
                    command=envelope.command,
                    correlation_id=envelope.correlation_id,
                    data={"error": str(exc)},
                )
            handle_time = time.time() - handle_start
            LOGGER.info("[GATEWAY] Handled request %s in %.3fs", envelope.id[:8], handle_time)
            self._metrics.observe(
                "gateway_handle_seconds",
                handle_time,
                labels={"command": envelope.command or "unknown"},
                buckets=DEFAULT_LATENCY_BUCKETS,
            )

            send_start = time.time()
            LOGGER.info("[GATEWAY] Sending response %s to %s", response.id[:8], sender)
            try:
                self.transport.send_message(response, sender)
            except Exception as exc:
                LOGGER.warning(
                    "[GATEWAY] Failed to send response %s to %s: %s",
                    response.id[:8],
                    sender,
                    exc,
                    exc_info=True,
                )
                self._metrics.inc(
                    "gateway_requests_total",
                    labels={
                        "command": response.command or "unknown",
                        "status": "send_failed",
                    },
                )
                return
            send_time = time.time() - send_start
            self._metrics.observe(
                "gateway_send_seconds",
                send_time,
                labels={"command": envelope.command or "unknown"},
                buckets=DEFAULT_LATENCY_BUCKETS,
            )

            total_time = time.time() - request_start
            LOGGER.info(
                "[GATEWAY] Completed request %s: total %.3fs (handle: %.3fs, send: %.3fs)",
                envelope.id[:8],
                total_time,
                handle_time,
                send_time,
            )
            self._metrics.observe(
                "gateway_total_seconds",
                total_time,
                labels={"command": envelope.command or "unknown"},
                buckets=DEFAULT_LATENCY_BUCKETS,
            )
            self._metrics.inc(
                "gateway_requests_total",
                labels={"command": envelope.command or "unknown", "status": "success"},
            )
        finally:
            self.transport.deduper.release_lease(
                in_progress_key, lease_seconds=lease_duration, remember=True
            )
            self._metrics.gauge("gateway_inflight_requests").dec(1)

    def run_forever(self, poll_interval: float = 0.1) -> None:
        self._running = True
        while self._running:
            self.run_once(timeout=poll_interval)

    def stop(self) -> None:
        self._running = False
        self._cleanup_event_loop()

    def _ensure_event_loop(self) -> None:
        """Create a persistent event loop in a background thread if one doesn't exist."""
        with self._loop_lock:
            if self._loop is not None and self._loop.is_running():
                return
            if not _ATLAS_CLIENT_AVAILABLE:
                raise RuntimeError(
                    "AtlasCommandHttpClient dependency is missing. "
                    "Install atlas_asset_http_client_python to enable gateway mode."
                )

            loop_started = threading.Event()

            def run_loop(loop: asyncio.AbstractEventLoop) -> None:
                asyncio.set_event_loop(loop)
                # Signal that the loop is about to start
                loop.call_soon(loop_started.set)
                loop.run_forever()

            self._loop = asyncio.new_event_loop()
            self._loop_thread = threading.Thread(
                target=run_loop,
                args=(self._loop,),
                daemon=True,
                name="gateway-event-loop",
            )
            self._loop_thread.start()

            # Wait for the event loop to actually start running (with timeout)
            if not loop_started.wait(timeout=5.0):
                raise RuntimeError("Event loop failed to start within 5 seconds")

            # Create HTTP client (it's created synchronously, but we need to enter async context)
            self._client = AtlasCommandHttpClient(self.api_base_url, token=self.token)

            async def enter_client() -> None:
                if self._client is not None:
                    await self._client.__aenter__()

            try:
                asyncio.run_coroutine_threadsafe(enter_client(), self._loop).result(
                    timeout=self._DEFAULT_LOOP_START_TIMEOUT
                )
            except FuturesTimeoutError as exc:
                self._loop.call_soon_threadsafe(self._loop.stop)
                raise RuntimeError(
                    f"HTTP client failed to start within {self._DEFAULT_LOOP_START_TIMEOUT}s"
                ) from exc

    def _cleanup_event_loop(self) -> None:
        """Clean up the event loop and HTTP client."""
        with self._loop_lock:
            if self._loop is not None:

                async def cleanup() -> None:
                    if self._client is not None:
                        await self._client.__aexit__(None, None, None)
                        self._client = None

                if self._loop.is_running():
                    try:
                        asyncio.run_coroutine_threadsafe(cleanup(), self._loop).result(timeout=5.0)
                    except Exception:
                        LOGGER.warning("[GATEWAY] Failed to cleanup HTTP client gracefully")
                    self._loop.call_soon_threadsafe(self._loop.stop)

                if self._loop_thread is not None:
                    self._loop_thread.join(timeout=2.0)
                    if self._loop_thread.is_alive():
                        LOGGER.warning("[GATEWAY] Event loop thread did not stop within timeout")
                        # Don't close the loop if thread is still running
                    else:
                        # Only close if the loop is no longer running
                        if not self._loop.is_running():
                            self._loop.close()

                self._loop = None
                self._loop_thread = None
                self._client = None

    def _handle_request(self, envelope: MessageEnvelope) -> MessageEnvelope:
        try:
            operation_name = self.command_map.get(envelope.command)
            if not operation_name:
                raise ValueError(f"Unknown command: {envelope.command}")

            module = self._load_operation(operation_name)
            result = self._run_operation(module, envelope.data or {}, envelope)
            compacted = self._compact_payload({"result": result})
            return MessageEnvelope(
                id=envelope.id,
                type="response",
                command=envelope.command,
                correlation_id=envelope.correlation_id,
                data=compacted,
            )
        except Exception as exc:
            LOGGER.exception("Failed to run %s", envelope.command)
            return MessageEnvelope(
                id=envelope.id,
                type="error",
                command=envelope.command,
                correlation_id=envelope.correlation_id,
                data={"error": str(exc)},
            )

    def _load_operation(self, name: str):
        try:
            return import_module(f".operations.{name}", package=__package__)
        except ModuleNotFoundError as exc:
            raise ValueError(f"Operation '{name}' is not implemented") from exc

    def _run_operation(self, module: Any, data: Dict[str, Any], envelope: MessageEnvelope) -> Any:
        """Run an operation using the persistent event loop and HTTP client."""
        self._ensure_event_loop()
        if self._loop is None or self._client is None:
            raise RuntimeError("Event loop not initialized")

        timeout_seconds = float(
            (envelope.meta or {}).get("operation_timeout_seconds", self._DEFAULT_OPERATION_TIMEOUT)
        )

        async def _inner() -> Any:
            return await module.run(self._client, envelope, data)

        future = asyncio.run_coroutine_threadsafe(_inner(), self._loop)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError as exc:
            future.cancel()
            raise TimeoutError(
                f"Gateway operation {envelope.command} exceeded {timeout_seconds}s"
            ) from exc

    def _call_api(self, method_name: str, data: Dict[str, Any]) -> Any:
        """Call an API method using the persistent event loop and HTTP client."""
        self._ensure_event_loop()
        if self._loop is None or self._client is None:
            raise RuntimeError("Event loop not initialized")

        timeout_seconds = float(data.get("timeout_seconds", self._DEFAULT_OPERATION_TIMEOUT))

        async def _inner() -> Any:
            handler = getattr(self._client, method_name)
            return await handler(**data)

        future = asyncio.run_coroutine_threadsafe(_inner(), self._loop)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError as exc:
            future.cancel()
            raise TimeoutError(
                f"Gateway API call {method_name} exceeded {timeout_seconds}s"
            ) from exc

    def _compact_payload(self, payload: Any) -> Any:
        if isinstance(payload, dict):
            compacted: Dict[str, Any] = {}
            for key, value in payload.items():
                compact_value = self._compact_payload(value)
                if compact_value is None:
                    continue
                compacted[key] = compact_value
            return compacted
        if isinstance(payload, list):
            return [self._compact_payload(item) for item in payload]
        return payload
