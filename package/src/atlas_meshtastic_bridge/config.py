from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BridgeConfig:
    mode: str
    gateway_node_id: str
    api_base_url: str
    api_token: str | None = None
    simulate_radio: bool = False
    timeout: float = 5.0
    spool_path: str | None = None
    metrics_host: str = "0.0.0.0"
    metrics_port: int = 9700
    metrics_enabled: bool = True
    # CLI-only fields (set by parse_args, not constructor arguments)
    _command: str | None = field(default=None, repr=False)
    _data: str = field(default="{}", repr=False)
    _radio_port: str | None = field(default=None, repr=False)
    _node_id: str | None = field(default=None, repr=False)
