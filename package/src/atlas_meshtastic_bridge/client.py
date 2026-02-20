from __future__ import annotations

import logging
import random
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from atlas_asset_http_client_python.components import (
    EntityComponents,
    TaskComponents,
    components_to_dict,
)

from .message import MessageEnvelope
from .metrics import DEFAULT_LATENCY_BUCKETS, get_metrics_registry
from .transport import MeshtasticTransport

LOGGER = logging.getLogger(__name__)
BACKOFF_BASE_SECONDS = 0.5
BACKOFF_JITTER_FACTOR = 0.2
BACKOFF_MAX_SECONDS = 30.0

EntityComponentsInput = Optional[EntityComponents]
TaskComponentsInput = Optional[TaskComponents]


class MeshtasticClient:
    def __init__(
        self,
        transport: MeshtasticTransport,
        gateway_node_id: str,
    ) -> None:
        self.transport = transport
        self.gateway_node_id = gateway_node_id
        self._metrics = get_metrics_registry()

    # Typed helper methods -------------------------------------------------
    def test_echo(
        self,
        message: Any = "ping",
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        return self._send_typed("test_echo", {"message": message}, timeout, max_retries)

    def health_check(
        self,
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        return self._send_typed("health_check", {}, timeout, max_retries)

    def list_entities(
        self,
        *,
        limit: int = 5,
        offset: int = 0,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        return self._send_typed(
            "list_entities", {"limit": limit, "offset": offset}, timeout, max_retries
        )

    def create_entity(
        self,
        entity_id: str,
        entity_type: str,
        alias: str,
        subtype: str,
        *,
        components: EntityComponentsInput = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        for field_name, value in (
            ("entity_id", entity_id),
            ("entity_type", entity_type),
            ("alias", alias),
            ("subtype", subtype),
        ):
            if not value:
                raise ValueError(f"create_entity requires '{field_name}'")
        payload: Dict[str, Any] = {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "alias": alias,
            "subtype": subtype,
        }
        comp_dict = components_to_dict(components)
        if comp_dict is not None:
            payload["components"] = comp_dict
        return self._send_typed("create_entity", payload, timeout, max_retries)

    def get_entity(
        self,
        entity_id: str,
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not entity_id:
            raise ValueError("get_entity requires 'entity_id'")
        return self._send_typed("get_entity", {"entity_id": entity_id}, timeout, max_retries)

    def get_entity_by_alias(
        self,
        alias: str,
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not alias:
            raise ValueError("get_entity_by_alias requires 'alias'")
        return self._send_typed("get_entity_by_alias", {"alias": alias}, timeout, max_retries)

    def update_entity(
        self,
        entity_id: str,
        *,
        subtype: Optional[str] = None,
        components: EntityComponentsInput = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not entity_id:
            raise ValueError("update_entity requires 'entity_id'")
        payload: Dict[str, Any] = {"entity_id": entity_id}
        if subtype is not None:
            payload["subtype"] = subtype
        comp_dict = components_to_dict(components)
        if comp_dict is not None:
            payload["components"] = comp_dict
        if len(payload) == 1:
            raise ValueError("update_entity requires at least one of: subtype, components")
        return self._send_typed("update_entity", payload, timeout, max_retries)

    def delete_entity(
        self,
        entity_id: str,
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not entity_id:
            raise ValueError("delete_entity requires 'entity_id'")
        return self._send_typed("delete_entity", {"entity_id": entity_id}, timeout, max_retries)

    def checkin_entity(
        self,
        entity_id: str,
        *,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        altitude_m: Optional[float] = None,
        speed_m_s: Optional[float] = None,
        heading_deg: Optional[float] = None,
        status_filter: str = "pending,in_progress",
        limit: int = 10,
        since: Optional[str | datetime] = None,
        fields: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not entity_id:
            raise ValueError("checkin_entity requires 'entity_id'")
        payload: Dict[str, Any] = {
            "entity_id": entity_id,
            "status_filter": status_filter,
            "limit": limit,
        }
        if since is not None:
            payload["since"] = since.isoformat() if isinstance(since, datetime) else since
        if fields is not None:
            payload["fields"] = fields
        for key, value in (
            ("latitude", latitude),
            ("longitude", longitude),
            ("altitude_m", altitude_m),
            ("speed_m_s", speed_m_s),
            ("heading_deg", heading_deg),
        ):
            if value is not None:
                payload[key] = value
        return self._send_typed("checkin_entity", payload, timeout, max_retries)

    def update_telemetry(
        self,
        entity_id: str,
        *,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        altitude_m: Optional[float] = None,
        speed_m_s: Optional[float] = None,
        heading_deg: Optional[float] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not entity_id:
            raise ValueError("update_telemetry requires 'entity_id'")
        payload: Dict[str, Any] = {"entity_id": entity_id}
        for key, value in (
            ("latitude", latitude),
            ("longitude", longitude),
            ("altitude_m", altitude_m),
            ("speed_m_s", speed_m_s),
            ("heading_deg", heading_deg),
        ):
            if value is not None:
                payload[key] = value
        if len(payload) == 1:
            raise ValueError("update_telemetry requires at least one telemetry field")
        return self._send_typed("update_telemetry", payload, timeout, max_retries)

    def list_tasks(
        self,
        *,
        status: Optional[str] = None,
        limit: int = 25,
        offset: int = 0,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        payload: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            payload["status"] = status
        return self._send_typed("list_tasks", payload, timeout, max_retries)

    def create_task(
        self,
        task_id: str,
        *,
        status: Optional[str] = None,
        entity_id: Optional[str] = None,
        components: TaskComponentsInput = None,
        extra: Optional[Any] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not task_id:
            raise ValueError("create_task requires 'task_id'")
        payload: Dict[str, Any] = {"task_id": task_id}
        if status is not None:
            payload["status"] = status
        if entity_id is not None:
            payload["entity_id"] = entity_id
        comp_dict = components_to_dict(components)
        if comp_dict is not None:
            payload["components"] = comp_dict
        if extra is not None:
            payload["extra"] = extra
        return self._send_typed("create_task", payload, timeout, max_retries)

    def get_task(
        self,
        task_id: str,
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not task_id:
            raise ValueError("get_task requires 'task_id'")
        return self._send_typed("get_task", {"task_id": task_id}, timeout, max_retries)

    def get_tasks_by_entity(
        self,
        entity_id: str,
        *,
        limit: int = 25,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not entity_id:
            raise ValueError("get_tasks_by_entity requires 'entity_id'")
        return self._send_typed(
            "get_tasks_by_entity",
            {"entity_id": entity_id, "limit": limit},
            timeout,
            max_retries,
        )

    def update_task(
        self,
        task_id: str,
        *,
        status: Optional[str] = None,
        entity_id: Optional[str] = None,
        components: TaskComponentsInput = None,
        extra: Optional[Any] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not task_id:
            raise ValueError("update_task requires 'task_id'")
        payload: Dict[str, Any] = {"task_id": task_id}
        if status is not None:
            payload["status"] = status
        if entity_id is not None:
            payload["entity_id"] = entity_id
        comp_dict = components_to_dict(components)
        if comp_dict is not None:
            payload["components"] = comp_dict
        if extra is not None:
            payload["extra"] = extra
        if len(payload) == 1:
            raise ValueError(
                "update_task requires at least one of: status, entity_id, components, extra"
            )
        return self._send_typed("update_task", payload, timeout, max_retries)

    def delete_task(
        self,
        task_id: str,
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not task_id:
            raise ValueError("delete_task requires 'task_id'")
        return self._send_typed("delete_task", {"task_id": task_id}, timeout, max_retries)

    def transition_task_status(
        self,
        task_id: str,
        status: str,
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not task_id or not status:
            raise ValueError("transition_task_status requires 'task_id' and 'status'")
        return self._send_typed(
            "transition_task_status",
            {"task_id": task_id, "status": status},
            timeout,
            max_retries,
        )

    def start_task(
        self,
        task_id: str,
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not task_id:
            raise ValueError("start_task requires 'task_id'")
        return self._send_typed("start_task", {"task_id": task_id}, timeout, max_retries)

    def complete_task(
        self,
        task_id: str,
        *,
        result: Optional[Any] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not task_id:
            raise ValueError("complete_task requires 'task_id'")
        payload: Dict[str, Any] = {"task_id": task_id}
        if result is not None:
            payload["result"] = result
        return self._send_typed("complete_task", payload, timeout, max_retries)

    def fail_task(
        self,
        task_id: str,
        *,
        error_message: Optional[str] = None,
        error_details: Optional[Any] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not task_id:
            raise ValueError("fail_task requires 'task_id'")
        payload: Dict[str, Any] = {"task_id": task_id}
        if error_message is not None:
            payload["error_message"] = error_message
        if error_details is not None:
            payload["error_details"] = error_details
        return self._send_typed("fail_task", payload, timeout, max_retries)

    def list_objects(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        content_type: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        payload: Dict[str, Any] = {"limit": limit, "offset": offset}
        if content_type:
            payload["content_type"] = content_type
        return self._send_typed("list_objects", payload, timeout, max_retries)

    def create_object(
        self,
        object_id: str,
        *,
        content_b64: str,
        usage_hint: Optional[str] = None,
        content_type: str,
        file_name: Optional[str] = None,
        type: Optional[str] = None,
        referenced_by: Optional[list[dict[str, Any]]] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not object_id:
            raise ValueError("create_object requires 'object_id'")
        if not content_b64:
            raise ValueError("create_object requires 'content_b64'")
        if not content_type:
            raise ValueError("create_object requires 'content_type'")
        payload: Dict[str, Any] = {"object_id": object_id, "content_b64": content_b64}
        if usage_hint is not None:
            payload["usage_hint"] = usage_hint
        payload["content_type"] = content_type
        if file_name is not None:
            payload["file_name"] = file_name
        if type is not None:
            payload["type"] = type
        if referenced_by is not None:
            payload["referenced_by"] = referenced_by
        return self._send_typed("create_object", payload, timeout, max_retries)

    def update_object(
        self,
        object_id: str,
        *,
        usage_hints: Optional[list[str]] = None,
        referenced_by: Optional[list[dict[str, Any]]] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not object_id:
            raise ValueError("update_object requires 'object_id'")
        payload: Dict[str, Any] = {"object_id": object_id}
        if usage_hints is not None:
            payload["usage_hints"] = usage_hints
        if referenced_by is not None:
            payload["referenced_by"] = referenced_by
        if len(payload) == 1:
            raise ValueError("update_object requires at least one of: usage_hints, referenced_by")
        return self._send_typed("update_object", payload, timeout, max_retries)

    def delete_object(
        self,
        object_id: str,
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not object_id:
            raise ValueError("delete_object requires 'object_id'")
        return self._send_typed("delete_object", {"object_id": object_id}, timeout, max_retries)

    def get_object(
        self,
        object_id: str,
        *,
        download: bool = False,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not object_id:
            raise ValueError("get_object requires 'object_id'")
        payload: Dict[str, Any] = {"object_id": object_id}
        if download:
            payload["download"] = True
        return self._send_typed("get_object", payload, timeout, max_retries)

    def add_object_reference(
        self,
        object_id: str,
        *,
        entity_id: Optional[str] = None,
        task_id: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not object_id:
            raise ValueError("add_object_reference requires 'object_id'")
        if not entity_id and not task_id:
            raise ValueError("add_object_reference requires 'entity_id' or 'task_id'")
        payload: Dict[str, Any] = {"object_id": object_id}
        if entity_id is not None:
            payload["entity_id"] = entity_id
        if task_id is not None:
            payload["task_id"] = task_id
        return self._send_typed("add_object_reference", payload, timeout, max_retries)

    def remove_object_reference(
        self,
        object_id: str,
        *,
        entity_id: Optional[str] = None,
        task_id: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not object_id:
            raise ValueError("remove_object_reference requires 'object_id'")
        if not entity_id and not task_id:
            raise ValueError("remove_object_reference requires 'entity_id' or 'task_id'")
        payload: Dict[str, Any] = {"object_id": object_id}
        if entity_id is not None:
            payload["entity_id"] = entity_id
        if task_id is not None:
            payload["task_id"] = task_id
        return self._send_typed("remove_object_reference", payload, timeout, max_retries)

    def find_orphaned_objects(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        return self._send_typed(
            "find_orphaned_objects",
            {"limit": limit, "offset": offset},
            timeout,
            max_retries,
        )

    def get_object_references(
        self,
        object_id: str,
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not object_id:
            raise ValueError("get_object_references requires 'object_id'")
        return self._send_typed(
            "get_object_references", {"object_id": object_id}, timeout, max_retries
        )

    def validate_object_references(
        self,
        object_id: str,
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not object_id:
            raise ValueError("validate_object_references requires 'object_id'")
        return self._send_typed(
            "validate_object_references", {"object_id": object_id}, timeout, max_retries
        )

    def cleanup_object_references(
        self,
        object_id: str,
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not object_id:
            raise ValueError("cleanup_object_references requires 'object_id'")
        return self._send_typed(
            "cleanup_object_references", {"object_id": object_id}, timeout, max_retries
        )

    def get_objects_by_entity(
        self,
        entity_id: str,
        *,
        limit: int = 50,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not entity_id:
            raise ValueError("get_objects_by_entity requires 'entity_id'")
        return self._send_typed(
            "get_objects_by_entity",
            {"entity_id": entity_id, "limit": limit},
            timeout,
            max_retries,
        )

    def get_objects_by_task(
        self,
        task_id: str,
        *,
        limit: int = 50,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        if not task_id:
            raise ValueError("get_objects_by_task requires 'task_id'")
        return self._send_typed(
            "get_objects_by_task",
            {"task_id": task_id, "limit": limit},
            timeout,
            max_retries,
        )

    def get_changed_since(
        self,
        since: str | datetime,
        *,
        limit_per_type: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        since_value = since.isoformat() if isinstance(since, datetime) else since
        payload: Dict[str, Any] = {"since": since_value}
        if limit_per_type is not None:
            payload["limit_per_type"] = limit_per_type
        return self._send_typed("get_changed_since", payload, timeout, max_retries)

    def get_full_dataset(
        self,
        *,
        entity_limit: Optional[int] = None,
        task_limit: Optional[int] = None,
        object_limit: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> MessageEnvelope:
        payload: Dict[str, Any] = {}
        if entity_limit is not None:
            payload["entity_limit"] = entity_limit
        if task_limit is not None:
            payload["task_limit"] = task_limit
        if object_limit is not None:
            payload["object_limit"] = object_limit
        return self._send_typed("get_full_dataset", payload, timeout, max_retries)

    def _send_typed(
        self,
        command: str,
        data: Dict[str, Any],
        timeout: Optional[float],
        max_retries: Optional[int],
    ) -> MessageEnvelope:
        kwargs: Dict[str, Any] = {}
        if timeout is not None:
            kwargs["timeout"] = timeout
        if max_retries is not None:
            kwargs["max_retries"] = max_retries
        return self.send_request(command=command, data=data, **kwargs)

    def send_request(
        self,
        command: str,
        data: Dict[str, Any] | None = None,
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> MessageEnvelope:
        request_start = time.time()
        envelope = MessageEnvelope(
            id=uuid.uuid4().hex[:20],
            type="request",
            command=command,
            data=data or {},
        )

        data_size = len(str(data or {}).encode("utf-8"))
        LOGGER.info(
            "[CLIENT] Sending request %s: command=%s, data_size=%d bytes, timeout=%.1fs, max_retries=%d",
            envelope.id[:8],
            command,
            data_size,
            timeout,
            max_retries,
        )

        last_exception = None
        original_id = envelope.id  # Keep original ID for response matching

        self._metrics.inc(
            "client_requests_total",
            labels={"command": command, "status": "started"},
        )

        for attempt in range(max_retries + 1):
            if attempt > 0:
                # Adaptive exponential backoff with jitter
                backoff = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                backoff += random.uniform(0, backoff * BACKOFF_JITTER_FACTOR)
                backoff = min(backoff, BACKOFF_MAX_SECONDS)
                LOGGER.info(
                    "[CLIENT] Retry attempt %d/%d for request %s (backoff %.2fs)",
                    attempt,
                    max_retries,
                    original_id[:8],
                    backoff,
                )
                self._metrics.inc(
                    "client_retries_total",
                    labels={"command": command, "attempt": str(attempt)},
                )
                time.sleep(backoff)
                # Keep the same envelope ID for retries - responses may be delayed
                # The gateway may already have sent a response that's still in transit

            # Opportunistically flush any pending spool entries before sending
            if hasattr(self.transport, "tick"):
                self.transport.tick()
            elif hasattr(self.transport, "process_outbox"):
                self.transport.process_outbox()

            send_start = time.time()
            self.transport.send_message(envelope, self.gateway_node_id)
            send_time = time.time() - send_start
            self._metrics.observe(
                "client_send_seconds",
                send_time,
                labels={"command": command},
                buckets=DEFAULT_LATENCY_BUCKETS,
            )
            LOGGER.info(
                "[CLIENT] Request %s sent in %.3fs, waiting for response (timeout %.1fs)...",
                envelope.id[:8],
                send_time,
                timeout,
            )

            attempt_start = time.time()
            last_progress = attempt_start
            observed_chunk_total = 1  # Updated when we see chunk headers/ACKs
            poll_count = 0
            # Use time-since-progress as the primary timeout; cap with a generous overall limit.
            overall_deadline = attempt_start + (timeout + 60.0)

            while True:
                now = time.time()
                inactivity_deadline = last_progress + timeout

                if now >= inactivity_deadline:
                    elapsed = time.time() - attempt_start
                    LOGGER.warning(
                        "[CLIENT] Inactivity timeout waiting for %s after %.3fs (attempt %d/%d)",
                        envelope.id[:8],
                        elapsed,
                        attempt + 1,
                        max_retries + 1,
                    )
                    last_exception = TimeoutError(f"No response for {command} ({envelope.id})")
                    self._metrics.inc(
                        "client_requests_total",
                        labels={"command": command, "status": "timeout"},
                    )
                    break  # Break inner loop to retry

                if now >= overall_deadline:
                    elapsed = time.time() - attempt_start
                    LOGGER.warning(
                        "[CLIENT] Overall timeout waiting for %s after %.3fs (attempt %d/%d)",
                        envelope.id[:8],
                        elapsed,
                        attempt + 1,
                        max_retries + 1,
                    )
                    last_exception = TimeoutError(f"No response for {command} ({envelope.id})")
                    self._metrics.inc(
                        "client_requests_total",
                        labels={"command": command, "status": "timeout"},
                    )
                    break  # Break inner loop to retry

                remaining = min(inactivity_deadline, overall_deadline) - now
                wait_timeout = max(0.05, min(0.5, remaining))

                poll_count += 1
                if poll_count % 10 == 0:  # Log every 10 polls (~5 seconds)
                    elapsed = time.time() - attempt_start
                    LOGGER.debug(
                        "[CLIENT] Still waiting for response to %s (%.1fs elapsed, %.1fs since last progress, %.1fs remaining)",
                        envelope.id[:8],
                        elapsed,
                        elapsed - (last_progress - attempt_start),
                        remaining,
                    )

                # Drive transport (send pending chunks)
                if hasattr(self.transport, "tick"):
                    self.transport.tick()

                sender, response = self.transport.receive_message(timeout=wait_timeout)

                # Refresh progress if we saw chunks/ACKs for this message
                progress = self.transport.last_chunk_progress(original_id)
                if progress and progress.timestamp > last_progress:
                    last_progress = progress.timestamp
                    if progress.total:
                        observed_chunk_total = max(observed_chunk_total, progress.total)
                    LOGGER.debug(
                        "[CLIENT] Progress on %s: chunk %d/%d (ack=%s) at +%.2fs",
                        original_id[:8],
                        progress.seq,
                        progress.total,
                        progress.is_ack,
                        last_progress - attempt_start,
                    )

                if response is None:
                    continue

                receive_time = time.time() - request_start
                LOGGER.debug(
                    "[CLIENT] Received message: sender=%s, response_id=%s, response_type=%s, expected_id=%s (after %.3fs)",
                    sender,
                    response.id[:8] if response else None,
                    response.type if response else None,
                    envelope.id[:8],
                    receive_time,
                )

                # Only accept responses with matching request ID (use original ID)
                if response.id != original_id:
                    LOGGER.debug(
                        "[CLIENT] Response ID mismatch: got %s, expected %s (ignoring)",
                        response.id[:8],
                        original_id[:8],
                    )
                    continue
                # Only accept response or error types, not requests
                if response.type not in ("response", "error"):
                    LOGGER.debug(
                        "[CLIENT] Response type mismatch: got %s, expected response or error (ignoring)",
                        response.type,
                    )
                    continue
                # In point-to-point communication, accept any response with matching ID
                # (The request ID matching provides sufficient security)
                total_time = time.time() - request_start
                LOGGER.info(
                    "[CLIENT] Accepted response %s: type=%s, total time=%.3fs (attempt %d/%d)",
                    response.id[:8],
                    response.type,
                    total_time,
                    attempt + 1,
                    max_retries + 1,
                )
                self._metrics.observe(
                    "client_total_seconds",
                    total_time,
                    labels={"command": command, "status": response.type},
                    buckets=DEFAULT_LATENCY_BUCKETS,
                )
                self._metrics.inc(
                    "client_requests_total",
                    labels={
                        "command": command,
                        "status": "success" if response.type == "response" else "error",
                    },
                )
                return response

            # If we get here, we timed out - retry if we have retries left
            if attempt < max_retries:
                continue

        # All retries exhausted
        elapsed = time.time() - request_start
        LOGGER.error(
            "[CLIENT] All retries exhausted for request %s after %.3fs",
            envelope.id[:8],
            elapsed,
        )
        self._metrics.inc(
            "client_requests_total",
            labels={"command": command, "status": "failure"},
        )
        if last_exception:
            raise last_exception
        raise TimeoutError(f"No response for {command} ({envelope.id})")
