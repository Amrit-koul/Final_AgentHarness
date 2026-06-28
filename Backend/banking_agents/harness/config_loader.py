"""Compatibility shim around the generic explicit-path loader."""
from pathlib import Path
from agent_harness.config_loader import load_agent_contracts as _load, load_named_config, load_yaml

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
def load_agent_contracts(config_dir=None): return _load(Path(config_dir) if config_dir else CONFIG_DIR / "agents")
def load_control_config(name, default=None): return load_named_config(CONFIG_DIR, name, default)
