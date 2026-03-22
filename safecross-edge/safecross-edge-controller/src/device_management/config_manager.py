"""Intersection configuration loader with schema validation and hot-reload."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import jsonschema

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "config" / "schema.json"

# Keys whose values should be masked when logging.
_SENSITIVE_KEYS = frozenset({
    "snmp_community_write",
    "api_key",
    "device_key_path",
})


class ConfigManager:
    """Loads, validates, and serves the intersection configuration.

    Args:
        config_path: Path to the ``intersection.json`` file.
        schema_path: Path to the JSON Schema (auto-detected by default).
    """

    def __init__(
        self,
        config_path: str = "/etc/safecross/intersection.json",
        schema_path: str | None = None,
    ) -> None:
        self._config_path = config_path
        self._schema_path = schema_path or str(_SCHEMA_PATH)
        self._config: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> dict[str, Any]:
        """Read the JSON config, validate against the schema, and return it.

        Raises:
            FileNotFoundError: If the config file does not exist.
            ValueError: If the config fails schema validation.
        """
        raw = Path(self._config_path).read_text(encoding="utf-8")
        config = json.loads(raw)

        schema = json.loads(Path(self._schema_path).read_text(encoding="utf-8"))
        try:
            jsonschema.validate(instance=config, schema=schema)
        except jsonschema.ValidationError as exc:
            raise ValueError(
                f"Config validation failed: {exc.message} "
                f"(path: {'.'.join(str(p) for p in exc.absolute_path)})"
            ) from exc

        self._config = config
        self._log_config(config)
        return config

    def reload(self) -> dict[str, Any]:
        """Hot-reload: re-read the file and replace config atomically.

        Suitable for use as a ``SIGHUP`` handler target.
        """
        logger.info("Reloading config from %s", self._config_path)
        return self.load()

    @property
    def config(self) -> dict[str, Any]:
        """Currently loaded config (empty dict before ``load()``)."""
        return self._config

    def get_crosswalk(self, direction: str) -> dict[str, Any] | None:
        """Return the crossing entry whose ``crossing_id`` matches *direction*."""
        for crossing in self._config.get("crossings", []):
            if crossing.get("crossing_id") == direction:
                return crossing
        return None

    def get_crosswalk_for_phase(self, phase: int) -> dict[str, Any] | None:
        """Return the crossing entry for the given signal *phase* number."""
        for crossing in self._config.get("crossings", []):
            if crossing.get("signal_phase") == phase:
                return crossing
        return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _log_config(config: dict[str, Any], prefix: str = "") -> None:
        """Log all config values at INFO, masking sensitive fields."""
        for key, value in config.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                ConfigManager._log_config(value, prefix=full_key)
            elif isinstance(value, list):
                logger.info("config %s = [%d items]", full_key, len(value))
            elif key in _SENSITIVE_KEYS:
                logger.info("config %s = ****", full_key)
            else:
                logger.info("config %s = %s", full_key, value)
