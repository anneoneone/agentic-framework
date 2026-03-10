"""
AdapterRegistry — maps spec-ID strings to adapter classes.

Usage:
    from spec_to_test.adapters.registry import get_adapter
    adapter = get_adapter("ocpp")
"""
from __future__ import annotations

from .base import BaseAdapter
from .ocpp import OCPPAdapter

REGISTRY: dict[str, type[BaseAdapter]] = {
    "ocpp": OCPPAdapter,
}


def get_adapter(spec_id: str) -> BaseAdapter:
    """
    Instantiate and return the adapter for the given spec ID.

    Args:
        spec_id: Spec identifier string (e.g. "ocpp").

    Raises:
        ValueError: If spec_id is not registered.
    """
    cls = REGISTRY.get(spec_id.lower())
    if cls is None:
        available = ", ".join(sorted(REGISTRY.keys()))
        raise ValueError(
            f"Unknown spec adapter '{spec_id}'. Available: {available}"
        )
    return cls()


def list_adapters() -> list[str]:
    """Return sorted list of registered spec IDs."""
    return sorted(REGISTRY.keys())
