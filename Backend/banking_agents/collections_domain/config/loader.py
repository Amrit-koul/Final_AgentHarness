from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

_RULES_DIR = Path(__file__).parent / "rules"


def _merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge dict2 into dict1."""
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


@lru_cache(maxsize=1)
def load_signals_config() -> Dict[str, Any]:
    merged_config: Dict[str, Any] = {}
    
    if not _RULES_DIR.exists():
        return merged_config
        
    try:
        import yaml  # type: ignore
        for yaml_file in _RULES_DIR.glob("*.yaml"):
            text = yaml_file.read_text(encoding="utf-8")
            data = yaml.safe_load(text) or {}
            merged_config = _merge_dicts(merged_config, data)
        return merged_config
    except ImportError:
        # Fallback would go here if yaml missing, simplified for our env
        return {}


def get_config() -> Dict[str, Any]:
    return load_signals_config()


