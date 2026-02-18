"""Unit tests for BridgeConfig."""

from atlas_meshtastic_bridge.config import BridgeConfig


def test_bridge_config_creation() -> None:
    """Test creating a BridgeConfig with all parameters."""
    config = BridgeConfig(
        mode="gateway",
        gateway_node_id="!abc123",
        api_base_url="http://localhost:8000",
        api_token="test_token",
        simulate_radio=True,
        timeout=10.0,
    )

    assert config.mode == "gateway"
    assert config.gateway_node_id == "!abc123"
    assert config.api_base_url == "http://localhost:8000"
    assert config.api_token == "test_token"
    assert config.simulate_radio is True
    assert config.timeout == 10.0


def test_bridge_config_defaults() -> None:
    """Test BridgeConfig default values."""
    config = BridgeConfig(
        mode="client",
        gateway_node_id="!xyz789",
        api_base_url="http://example.com",
    )

    assert config.mode == "client"
    assert config.gateway_node_id == "!xyz789"
    assert config.api_base_url == "http://example.com"
    assert config.api_token is None
    assert config.simulate_radio is False
    assert config.timeout == 5.0
