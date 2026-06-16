"""
Unified configuration loader.

Single source of truth for reading/writing config.json.
All modules MUST use this instead of reading the file directly.
"""

import json
import os
import tempfile
from functools import lru_cache
from typing import Any, Dict

from app._paths import data_dir

_CONFIG_PATH = data_dir("config.json")


@lru_cache(maxsize=1)
def load_raw_config() -> Dict[str, Any]:
    """Read config.json once per process, cached forever.

    Call clear_config_cache() to invalidate (for tests or after write).
    """
    if not os.path.exists(_CONFIG_PATH):
        return {}
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_raw_config(data: Dict[str, Any]) -> None:
    """Atomically write config.json and invalidate cache."""
    os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".tmp", delete=False,
        dir=os.path.dirname(_CONFIG_PATH), encoding="utf-8"
    ) as tf:
        json.dump(data, tf, ensure_ascii=False, indent=2)
        tmp_name = tf.name
    os.replace(tmp_name, _CONFIG_PATH)  # atomic on POSIX; best-effort on Windows
    clear_config_cache()


def clear_config_cache() -> None:
    """Invalidate the config cache (call after save)."""
    load_raw_config.cache_clear()
