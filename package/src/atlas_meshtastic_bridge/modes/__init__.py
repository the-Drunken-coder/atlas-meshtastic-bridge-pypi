"""
Mode profiles for the Meshtastic bridge.

Modes bundle recommended defaults (reliability strategy, timeouts, and
transport tuning) so consumers can pick a single name instead of
managing many knobs. Profiles live alongside this module as JSON files.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Dict, Iterable

from typing_extensions import TypedDict


class ModeProfile(TypedDict, total=False):
    """Shape of a mode profile loaded from JSON."""

    name: str
    description: str
    reliability_method: str
    modem_preset: str
    timeout: float
    retries: int
    post_response_timeout: float
    post_response_quiet: float
    transport: Dict[str, object]


def _load_raw_mode(path: str) -> ModeProfile:
    with resources.files(__package__).joinpath(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Mode file {path} did not contain an object")
    return data  # type: ignore[return-value]


def load_mode_profile(name: str) -> ModeProfile:
    """
    Load a mode by name.

    The mode name should correspond to ``<name>.json`` in this package.
    """
    filename = f"{name}.json"
    return _load_raw_mode(filename)


def list_modes() -> Iterable[str]:
    """Return available mode names (without .json)."""
    for entry in resources.files(__package__).iterdir():
        if entry.name.endswith(".json"):
            yield entry.name.rsplit(".", 1)[0]


__all__ = ["ModeProfile", "load_mode_profile", "list_modes"]
