"""Tests for components coercion module."""

from unittest.mock import patch

import pytest
from atlas_asset_http_client_python.components import EntityComponents, TaskComponents
from atlas_meshtastic_bridge.operations.components import (
    coerce_entity_components,
    coerce_task_components,
)


def test_coerce_entity_components_with_valid_dict():
    """Entity mapping payloads are coerced to typed components."""
    components_dict = {
        "custom_asset_type": "drone",
        "custom_manufacturer": "Test Corp",
    }

    result = coerce_entity_components(components_dict)
    assert isinstance(result, EntityComponents)


def test_coerce_task_components_with_valid_dict():
    """Task mapping payloads are coerced to typed components."""
    components_dict = {
        "custom_priority": "high",
        "custom_deadline": "2024-01-01T00:00:00Z",
    }

    result = coerce_task_components(components_dict)
    assert isinstance(result, TaskComponents)


def test_coerce_entity_components_with_typed_input():
    """Typed entity components pass through unchanged."""
    components = EntityComponents(custom_asset_type="drone")
    assert coerce_entity_components(components) is components


def test_coerce_task_components_with_typed_input():
    """Typed task components pass through unchanged."""
    components = TaskComponents(custom_priority="high")
    assert coerce_task_components(components) is components


def test_coerce_entity_components_with_none():
    """None is allowed."""
    result = coerce_entity_components(None)
    assert result is None


def test_coerce_task_components_with_none():
    """None is allowed."""
    result = coerce_task_components(None)
    assert result is None


def test_coerce_entity_components_rejects_non_mapping():
    """Raw non-mapping values are rejected."""
    with pytest.raises(TypeError, match="Components must be provided"):
        coerce_entity_components("not a dict")

    with pytest.raises(TypeError, match="Components must be provided"):
        coerce_entity_components(123)


def test_coerce_task_components_rejects_non_mapping():
    """Raw non-mapping values are rejected."""
    with pytest.raises(TypeError, match="Components must be provided"):
        coerce_task_components("not a dict")

    with pytest.raises(TypeError, match="Components must be provided"):
        coerce_task_components(123)


def test_coerce_entity_components_handles_invalid_data():
    """Unknown component keys raise a coercion error."""
    invalid_components = {
        "unknown_field": "value",
        "another_unknown": 123,
    }

    with pytest.raises(TypeError, match="Failed to coerce"):
        coerce_entity_components(invalid_components)


def test_coerce_task_components_handles_invalid_data():
    """Unknown task component keys raise a coercion error."""
    components_with_extra_fields = {
        "unknown_field": "value",
        "another_unknown": 123,
    }

    with pytest.raises(TypeError, match="Failed to coerce"):
        coerce_task_components(components_with_extra_fields)


@patch("atlas_meshtastic_bridge.operations.components.EntityComponents")
def test_coerce_entity_components_with_mock_model(mock_entity_components):
    """Coercion works with mocked EntityComponents model."""
    components_dict = {"custom_asset_type": "drone"}

    mock_instance = {"custom_asset_type": "drone", "mocked": True}
    mock_entity_components.return_value = mock_instance

    result = coerce_entity_components(components_dict)

    mock_entity_components.assert_called_once_with(**components_dict)
    assert result == mock_instance


@patch("atlas_meshtastic_bridge.operations.components.EntityComponents")
def test_coerce_entity_components_with_mock_model_error(mock_entity_components):
    """Model constructor errors are wrapped as TypeError."""
    components_dict = {"custom_asset_type": "drone"}

    mock_entity_components.side_effect = TypeError("Invalid field")

    with pytest.raises(TypeError, match="Failed to coerce"):
        coerce_entity_components(components_dict)


@patch("atlas_meshtastic_bridge.operations.components.TaskComponents")
def test_coerce_task_components_with_mock_model(mock_task_components):
    """Coercion works with mocked TaskComponents model."""
    components_dict = {"custom_priority": "high"}

    mock_instance = {"custom_priority": "high", "mocked": True}
    mock_task_components.return_value = mock_instance

    result = coerce_task_components(components_dict)

    mock_task_components.assert_called_once_with(**components_dict)
    assert result == mock_instance


@patch("atlas_meshtastic_bridge.operations.components.TaskComponents")
def test_coerce_task_components_with_mock_model_error(mock_task_components):
    """Model constructor errors are wrapped as TypeError."""
    components_dict = {"custom_priority": "high"}

    mock_task_components.side_effect = ValueError("Invalid value")

    with pytest.raises(TypeError, match="Failed to coerce"):
        coerce_task_components(components_dict)
