from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Type

try:
    from atlas_asset_http_client_python.components import (
        EntityComponents as _EntityComponents,
    )
    from atlas_asset_http_client_python.components import (
        TaskComponents as _TaskComponents,
    )
except (
    ImportError,
    ModuleNotFoundError,
):  # pragma: no cover - optional dependency for typed helpers
    EntityComponents: Optional[Type[Any]] = None
    TaskComponents: Optional[Type[Any]] = None
else:
    EntityComponents = _EntityComponents
    TaskComponents = _TaskComponents

LOGGER = logging.getLogger(__name__)


def _coerce_components(
    components: Any,
    model: Optional[Type[Any]],
) -> Any:
    if components is None:
        return None
    if model is None:
        raise RuntimeError(
            "Typed components support is not available. "
            "Ensure the 'atlas-asset-client' dependency is installed."
        )
    try:
        if isinstance(components, model):
            return components
    except TypeError:
        # Some tests patch model with a non-type mock. Fall through to constructor path.
        pass

    if not isinstance(components, Mapping):
        model_name = getattr(model, "__name__", repr(model))
        raise TypeError(
            f"Components must be provided as {model_name} or a mapping payload, "
            f"got {type(components).__name__}."
        )

    # Attempt to coerce the mapping into the typed model. On failure, raise a clear
    # exception that preserves the original error for easier debugging.
    try:
        return model(**components)
    except Exception as exc:
        model_name = getattr(model, "__name__", repr(model))
        LOGGER.debug("Failed to coerce component mapping into %s", model_name, exc_info=True)
        raise TypeError(f"Failed to coerce components mapping into {model_name}: {exc}") from exc


def coerce_entity_components(components: Any) -> Any:
    return _coerce_components(components, EntityComponents)


def coerce_task_components(components: Any) -> Any:
    return _coerce_components(components, TaskComponents)
