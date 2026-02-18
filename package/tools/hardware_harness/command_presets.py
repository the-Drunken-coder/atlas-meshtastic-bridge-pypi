from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List

from atlas_meshtastic_bridge.client import MeshtasticClient

# Shared command definitions for the harness interactive menu
COMMAND_PRESETS: Dict[str, Dict[str, Any]] = {
    # === Entities ===
    "list_entities": {
        "description": "List entities (may be filtered by limit/offset)",
        "fields": [
            {"name": "limit", "prompt": "Limit", "default": 5, "type": "int"},
            {"name": "offset", "prompt": "Offset", "default": 0, "type": "int"},
        ],
    },
    "create_entity": {
        "description": "Create an entity",
        "fields": [
            {"name": "entity_id", "prompt": "Entity ID"},
            {"name": "entity_type", "prompt": "Entity type"},
            {"name": "alias", "prompt": "Alias"},
            {"name": "subtype", "prompt": "Subtype"},
            {
                "name": "components",
                "prompt": "Components (JSON, blank to skip)",
                "type": None,
            },
        ],
    },
    "get_entity": {
        "description": "Fetch a specific entity by ID",
        "fields": [{"name": "entity_id", "prompt": "Entity ID"}],
    },
    "get_entity_by_alias": {
        "description": "Fetch entity by alias",
        "fields": [{"name": "alias", "prompt": "Alias"}],
    },
    "update_entity": {
        "description": "Update an entity subtype/components",
        "fields": [
            {"name": "entity_id", "prompt": "Entity ID"},
            {"name": "subtype", "prompt": "Subtype (blank to skip)"},
            {
                "name": "components",
                "prompt": "Components (JSON, blank to skip)",
                "type": None,
            },
        ],
    },
    "delete_entity": {
        "description": "Delete an entity",
        "fields": [
            {"name": "entity_id", "prompt": "Entity ID"},
        ],
    },
    "checkin_entity": {
        "description": "Send a check-in with optional telemetry",
        "fields": [
            {"name": "entity_id", "prompt": "Entity ID"},
            {"name": "latitude", "prompt": "Latitude (blank to skip)", "type": "float"},
            {
                "name": "longitude",
                "prompt": "Longitude (blank to skip)",
                "type": "float",
            },
            {
                "name": "altitude_m",
                "prompt": "Altitude (m, blank to skip)",
                "type": "float",
            },
            {
                "name": "speed_m_s",
                "prompt": "Speed m/s (blank to skip)",
                "type": "float",
            },
            {
                "name": "heading_deg",
                "prompt": "Heading deg (blank to skip)",
                "type": "float",
            },
            {
                "name": "status_filter",
                "prompt": "Status filter (default: pending,in_progress)",
            },
            {"name": "limit", "prompt": "Task limit (default: 10)", "type": "int"},
            {
                "name": "since",
                "prompt": "Since RFC3339 (blank to skip)",
            },
            {
                "name": "fields",
                "prompt": "Response fields (e.g., minimal; blank for full)",
            },
        ],
    },
    "update_telemetry": {
        "description": "Update telemetry only",
        "fields": [
            {"name": "entity_id", "prompt": "Entity ID"},
            {"name": "latitude", "prompt": "Latitude (blank to skip)", "type": "float"},
            {
                "name": "longitude",
                "prompt": "Longitude (blank to skip)",
                "type": "float",
            },
            {
                "name": "altitude_m",
                "prompt": "Altitude (m, blank to skip)",
                "type": "float",
            },
            {
                "name": "speed_m_s",
                "prompt": "Speed m/s (blank to skip)",
                "type": "float",
            },
            {
                "name": "heading_deg",
                "prompt": "Heading deg (blank to skip)",
                "type": "float",
            },
        ],
    },
    # === Tasks ===
    "list_tasks": {
        "description": "List tasks (optional status)",
        "fields": [
            {"name": "status", "prompt": "Status (blank to skip)"},
            {"name": "limit", "prompt": "Limit", "default": 25, "type": "int"},
        ],
    },
    "get_task": {
        "description": "Fetch a specific task",
        "fields": [{"name": "task_id", "prompt": "Task ID"}],
    },
    "create_task": {
        "description": "Create a task",
        "fields": [
            {"name": "task_id", "prompt": "Task ID"},
            {"name": "status", "prompt": "Status (blank for default pending)"},
            {"name": "entity_id", "prompt": "Entity ID (blank to skip)"},
            {
                "name": "components",
                "prompt": "Components (JSON, blank to skip)",
                "type": None,
            },
            {"name": "extra", "prompt": "Extra (JSON, blank to skip)", "type": None},
        ],
    },
    "update_task": {
        "description": "Update a task",
        "fields": [
            {"name": "task_id", "prompt": "Task ID"},
            {"name": "status", "prompt": "Status (blank to skip)"},
            {"name": "entity_id", "prompt": "Entity ID (blank to skip)"},
            {
                "name": "components",
                "prompt": "Components (JSON, blank to skip)",
                "type": None,
            },
            {"name": "extra", "prompt": "Extra (JSON, blank to skip)", "type": None},
        ],
    },
    "delete_task": {
        "description": "Delete a task",
        "fields": [{"name": "task_id", "prompt": "Task ID"}],
    },
    "transition_task_status": {
        "description": "Transition task status",
        "fields": [
            {"name": "task_id", "prompt": "Task ID"},
            {"name": "status", "prompt": "New status"},
        ],
    },
    "get_tasks_by_entity": {
        "description": "List tasks for an entity",
        "fields": [
            {"name": "entity_id", "prompt": "Entity ID"},
            {"name": "limit", "prompt": "Limit", "default": 5, "type": "int"},
        ],
    },
    "start_task": {
        "description": "Mark a task as started",
        "fields": [{"name": "task_id", "prompt": "Task ID"}],
    },
    "complete_task": {
        "description": "Complete a task (optional note)",
        "fields": [
            {"name": "task_id", "prompt": "Task ID"},
            {"name": "note", "prompt": "Note (blank to skip)"},
        ],
    },
    "fail_task": {
        "description": "Fail a task with an optional reason",
        "fields": [
            {"name": "task_id", "prompt": "Task ID"},
            {"name": "reason", "prompt": "Reason (blank to skip)"},
        ],
    },
    # === Objects ===
    "list_objects": {
        "description": "List objects",
        "fields": [
            {"name": "limit", "prompt": "Limit", "default": 20, "type": "int"},
            {"name": "offset", "prompt": "Offset", "default": 0, "type": "int"},
            {"name": "content_type", "prompt": "Content type filter (blank to skip)"},
        ],
    },
    "get_object": {
        "description": "Get object metadata or download",
        "fields": [
            {"name": "object_id", "prompt": "Object ID"},
            {
                "name": "download",
                "prompt": "Download content? (true/false)",
                "type": "bool",
            },
        ],
    },
    "update_object": {
        "description": "Update object metadata",
        "fields": [
            {"name": "object_id", "prompt": "Object ID"},
            {
                "name": "usage_hints",
                "prompt": "Usage hints (JSON array, blank to skip)",
                "type": None,
            },
            {
                "name": "referenced_by",
                "prompt": "Referenced by (JSON list, blank to skip)",
                "type": None,
            },
        ],
    },
    "delete_object": {
        "description": "Delete an object",
        "fields": [{"name": "object_id", "prompt": "Object ID"}],
    },
    "create_object": {
        "description": "Upload small object content (base64-encoded)",
        "fields": [
            {"name": "object_id", "prompt": "Object ID"},
            {
                "name": "file_name",
                "prompt": "File name (blank to default)",
                "type": None,
            },
            {"name": "file_path", "prompt": "File path (blank to skip)"},
            {"name": "content", "prompt": "Inline content (blank to skip)"},
            {
                "name": "size_kb",
                "prompt": "Generate file size KB if none provided (default 10KB)",
                "default": 10,
                "type": "int",
            },
            {
                "name": "content_type",
                "prompt": "Content type (required, e.g., text/plain)",
                "default": "text/plain",
                "type": None,
            },
            {"name": "type", "prompt": "Object type (blank to skip)", "type": None},
            {"name": "usage_hint", "prompt": "Usage hint (blank to skip)"},
        ],
    },
    "add_object_reference": {
        "description": "Add object reference",
        "fields": [
            {"name": "object_id", "prompt": "Object ID"},
            {"name": "entity_id", "prompt": "Entity ID (blank to skip)"},
            {"name": "task_id", "prompt": "Task ID (blank to skip)"},
        ],
    },
    "remove_object_reference": {
        "description": "Remove object reference",
        "fields": [
            {"name": "object_id", "prompt": "Object ID"},
            {"name": "entity_id", "prompt": "Entity ID (blank to skip)"},
            {"name": "task_id", "prompt": "Task ID (blank to skip)"},
        ],
    },
    "find_orphaned_objects": {
        "description": "Find orphaned objects",
        "fields": [
            {"name": "limit", "prompt": "Limit", "default": 100, "type": "int"},
            {"name": "offset", "prompt": "Offset", "default": 0, "type": "int"},
        ],
    },
    "get_object_references": {
        "description": "Get object reference info",
        "fields": [{"name": "object_id", "prompt": "Object ID"}],
    },
    "validate_object_references": {
        "description": "Validate object references",
        "fields": [{"name": "object_id", "prompt": "Object ID"}],
    },
    "cleanup_object_references": {
        "description": "Cleanup object references",
        "fields": [{"name": "object_id", "prompt": "Object ID"}],
    },
    # === Queries ===
    "get_changed_since": {
        "description": "Fetch incremental changes since a cursor",
        "fields": [
            {"name": "cursor", "prompt": "Cursor (ISO timestamp)"},
            {"name": "limit", "prompt": "Limit", "default": 50, "type": "int"},
        ],
    },
    "get_full_dataset": {
        "description": "Fetch full dataset (optional limits)",
        "fields": [
            {
                "name": "entity_limit",
                "prompt": "Entity limit (blank to skip)",
                "type": "int",
            },
            {
                "name": "task_limit",
                "prompt": "Task limit (blank to skip)",
                "type": "int",
            },
            {
                "name": "object_limit",
                "prompt": "Object limit (blank to skip)",
                "type": "int",
            },
        ],
    },
    # === Misc ===
    "test_echo": {
        "description": "Round-trip an echo payload to verify the link",
        "fields": [
            {
                "name": "message",
                "prompt": "Echo message",
                "default": "hello from harness",
            },
        ],
    },
    "auto_flight": {
        "description": "Simulate a 5-minute flight with periodic telemetry",
        "fields": [
            {
                "name": "duration_sec",
                "prompt": "Flight duration seconds",
                "default": 300,
                "type": "int",
            },
            {
                "name": "steps",
                "prompt": "Number of waypoints",
                "default": 10,
                "type": "int",
            },
        ],
    },
}

_DEFAULT_COUNTER = {"seq": 0}


def gen_default_id(prefix: str) -> str:
    _DEFAULT_COUNTER["seq"] += 1
    return f"{prefix}-{int(time.time())}-{_DEFAULT_COUNTER['seq']}"


def default_context() -> Dict[str, Any]:
    """Shared defaults across commands (last created/used ids)."""
    return {"entity_id": None, "task_id": None, "object_id": None}


def defaults_for_command(command: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Return default field values derived from prior actions."""
    entity_cmds = {
        "get_entity",
        "get_entity_by_alias",
        "update_entity",
        "delete_entity",
        "checkin_entity",
        "update_telemetry",
    }
    task_cmds = {
        "get_task",
        "update_task",
        "delete_task",
        "transition_task_status",
        "start_task",
        "complete_task",
        "fail_task",
    }
    object_cmds = {
        "get_object",
        "update_object",
        "delete_object",
        "add_object_reference",
        "remove_object_reference",
        "get_object_references",
        "validate_object_references",
        "cleanup_object_references",
    }
    defaults: Dict[str, Any] = {}
    if command == "create_entity":
        defaults.update(
            {
                "entity_id": context.get("entity_id") or gen_default_id("entity"),
                "entity_type": "asset",
                "alias": context.get("entity_id") or gen_default_id("alias"),
                "subtype": "generic",
            }
        )
    if command == "create_task":
        defaults["task_id"] = context.get("task_id") or gen_default_id("task")
        if context.get("entity_id"):
            defaults["entity_id"] = context["entity_id"]
    if command in entity_cmds or command == "create_task" or command == "get_tasks_by_entity":
        if context.get("entity_id"):
            defaults["entity_id"] = context["entity_id"]
    if command in task_cmds or command == "create_task":
        if context.get("task_id"):
            defaults["task_id"] = context["task_id"]
    if (
        command in object_cmds
        or command == "add_object_reference"
        or command == "remove_object_reference"
    ):
        if context.get("object_id"):
            defaults["object_id"] = context["object_id"]
    if command == "create_object" and context.get("object_id"):
        defaults["object_id"] = context["object_id"]
    return defaults


def apply_field_defaults(
    command: str, fields: List[Dict[str, Any]], context: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Overlay context-derived defaults onto prompt fields."""
    defaults = defaults_for_command(command, context)
    patched: List[Dict[str, Any]] = []
    for field in fields:
        updated = dict(field)
        name = updated.get("name")
        if name in defaults and defaults[name] is not None and updated.get("default") is None:
            updated["default"] = defaults[name]
        patched.append(updated)
    return patched


def update_context_from_payload(
    command: str, payload: Dict[str, Any], context: Dict[str, Any]
) -> None:
    """Capture ids from the last request so subsequent prompts can default to them."""
    if "entity_id" in payload and payload.get("entity_id"):
        context["entity_id"] = payload["entity_id"]
    if "task_id" in payload and payload.get("task_id"):
        context["task_id"] = payload["task_id"]
    if "object_id" in payload and payload.get("object_id"):
        context["object_id"] = payload["object_id"]


def generate_realistic_content(size_kb: int, content_type: str | None) -> bytes:
    """Generate sample content that compresses more like real data."""
    size_kb = max(1, size_kb)
    size_bytes = size_kb * 1024
    is_text = bool(content_type and (content_type.startswith("text/") or "json" in content_type))
    if not is_text:
        return os.urandom(size_bytes)

    lines: List[str] = []
    idx = 0
    while sum(len(line) for line in lines) < size_bytes:
        lines.append(
            json.dumps(
                {
                    "ts": int(time.time()) + idx,
                    "lat": 40.0 + 0.001 * (idx % 500),
                    "lon": -75.0 - 0.001 * (idx % 500),
                    "note": f"sample-{idx % 10}",
                }
            )
            + "\n"
        )
        idx += 1
    text = "".join(lines)
    return text[:size_bytes].encode("utf-8")


def run_auto_flight(
    client: MeshtasticClient,
    duration_sec: int,
    steps: int,
    context: Dict[str, Any],
    timeout: float,
    retries: int,
) -> None:
    """Simulate a simple flight: create entity if needed, then send periodic telemetry."""
    entity_id = context.get("entity_id") or gen_default_id("entity")
    try:
        client.create_entity(
            entity_id,
            entity_type="asset",
            alias=entity_id,
            subtype="drone",
            components={"telemetry": {"latitude": 40.0, "longitude": -75.0, "altitude_m": 100.0}},
            timeout=timeout,
            max_retries=retries,
        )
    except Exception:
        # Entity creation is best-effort for this harness; it may already exist or fail
        # in a non-critical way, so we continue using the entity_id regardless.
        pass
    context["entity_id"] = entity_id

    base_lat, base_lon = 40.0, -75.0
    leg = 0.01
    waypoints = [
        (base_lat, base_lon),
        (base_lat + leg, base_lon),
        (base_lat + leg, base_lon + leg),
        (base_lat, base_lon + leg),
        (base_lat, base_lon),
    ]
    if steps < len(waypoints):
        waypoints = waypoints[:steps]

    total_steps = max(steps, len(waypoints))
    interval = max(1.0, duration_sec / total_steps)

    start_time = time.time()
    for idx in range(total_steps):
        wp = waypoints[idx % len(waypoints)]
        lat, lon = wp
        alt = 100.0 + 2 * idx
        heading = (idx * 45) % 360
        print(f"[AUTO] Step {idx+1}/{total_steps}: lat={lat:.5f}, lon={lon:.5f}, alt={alt}")
        try:
            client.update_telemetry(
                entity_id,
                latitude=lat,
                longitude=lon,
                altitude_m=alt,
                speed_m_s=10.0,
                heading_deg=heading,
                timeout=timeout,
                max_retries=retries,
            )
        except Exception as exc:
            print(f"[AUTO] Telemetry update failed at step {idx+1}: {exc}")
        elapsed = time.time() - start_time
        remaining = (idx + 1) * interval - elapsed
        if remaining > 0:
            time.sleep(remaining)

    try:
        resp = client.get_entity(entity_id, timeout=timeout, max_retries=retries)
        print("[AUTO] Final entity snapshot:")
        print(json.dumps(resp.to_dict(), indent=2))
    except Exception as exc:
        print(f"[AUTO] Final entity fetch failed: {exc}")


__all__ = [
    "COMMAND_PRESETS",
    "apply_field_defaults",
    "default_context",
    "gen_default_id",
    "generate_realistic_content",
    "run_auto_flight",
    "update_context_from_payload",
]
