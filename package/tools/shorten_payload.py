#!/usr/bin/env python3
"""CLI helper to shorten payloads using the bridge aliasing rules."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any


def _ensure_package_imports() -> None:
    if __package__:
        return
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    bridge_root = os.path.abspath(os.path.join(tools_dir, ".."))
    src_path = os.path.join(bridge_root, "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


def shorten_payload(data: Any) -> Any:
    _ensure_package_imports()
    from atlas_meshtastic_bridge.message import shorten_payload as _shorten

    return _shorten(data)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Shorten a JSON payload using atlas_meshtastic_bridge aliasing rules."
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Path to JSON file (reads stdin if omitted)",
    )
    args = parser.parse_args()

    if args.path is None:
        if sys.stdin.isatty():
            print("Paste JSON, then press Enter on a blank line to finish:")
            lines = []
            while True:
                try:
                    line = input()
                except EOFError:
                    break
                if line == "":
                    break
                lines.append(line)
            raw = "\n".join(lines)
        else:
            raw = sys.stdin.read()
    else:
        with open(args.path, "r", encoding="utf-8") as f:
            raw = f.read()
    data = json.loads(raw)
    shortened = shorten_payload(data)
    json.dump(shortened, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
