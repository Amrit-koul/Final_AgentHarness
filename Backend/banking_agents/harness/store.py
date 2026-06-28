"""Compatibility shim; the store implementation is generic and its instance is bank-configured."""
from agent_harness.store import ControlPlaneStore

def __getattr__(name):
    if name == "control_store":
        from .runtime import control_plane
        return control_plane.store
    raise AttributeError(name)
