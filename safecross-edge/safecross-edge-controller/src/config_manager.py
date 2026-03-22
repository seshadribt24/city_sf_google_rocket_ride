"""Configuration manager for SafeCross Edge Controller.

Loads, validates, and provides typed access to the per-intersection
configuration JSON file using Pydantic models.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LocationConfig(BaseModel):
    """Geographic location of the intersection."""

    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class CrossingConfig(BaseModel):
    """Configuration for a single crosswalk at the intersection."""

    crossing_id: str
    description: str
    width_ft: float = Field(gt=0)
    signal_phase: int = Field(ge=1, le=16)
    base_walk_sec: int = Field(ge=1)
    base_clearance_sec: int = Field(ge=1)
    max_extension_sec: int = Field(ge=1)
    min_extension_sec: int = Field(ge=1)
    ped_detector_phase_bit: int = Field(ge=1)


class SignalControllerConfig(BaseModel):
    """SNMP/NTCIP connection settings for the traffic signal controller."""

    ip_address: str
    snmp_port: int = Field(default=161, ge=1, le=65535)
    snmp_community_read: str
    snmp_community_write: str
    protocol_version: str = "ntcip1202v02"
    controller_model: str = "econolite_cobalt"
    supports_scp: bool = False


class NFCReaderConfig(BaseModel):
    """RS-485 NFC reader connection settings."""

    serial_port: str
    baud_rate: int = 115200
    reader_id: str


class TimingRulesConfig(BaseModel):
    """Rules governing when and how walk phase extensions are granted."""

    cooldown_sec: int = Field(default=120, ge=0)
    max_extensions_per_cycle: int = Field(default=1, ge=1)
    extension_formula: str = "linear_by_width"
    eligible_card_types: list[str] = Field(default_factory=lambda: ["SENIOR_RTC", "DISABLED_RTC"])
    extend_during_active_walk: bool = True
    block_during_preemption: bool = True


class CloudConfig(BaseModel):
    """Cloud backend API connection settings."""

    api_url: str
    device_cert_path: str
    device_key_path: str
    heartbeat_interval_sec: int = Field(default=300, ge=10)
    event_batch_size: int = Field(default=10, ge=1)
    event_flush_interval_sec: int = Field(default=60, ge=1)


class OTAConfig(BaseModel):
    """Over-the-air update settings."""

    manifest_url: str
    check_interval_sec: int = Field(default=86400, ge=60)
    auto_apply: bool = False


class IntersectionConfig(BaseModel):
    """Top-level intersection configuration model.

    Validates the full per-intersection JSON configuration file and provides
    typed access to all settings.
    """

    intersection_id: str
    location: LocationConfig
    crossings: list[CrossingConfig] = Field(min_length=1)
    signal_controller: SignalControllerConfig
    nfc_reader: NFCReaderConfig
    timing_rules: TimingRulesConfig
    cloud: CloudConfig
    ota: OTAConfig


class ConfigManager:
    """Loads, validates, and manages the intersection configuration.

    Attributes:
        config: The validated IntersectionConfig instance.
        config_path: Path to the JSON configuration file.
    """

    def __init__(self, config: IntersectionConfig, config_path: Path) -> None:
        self.config = config
        self.config_path = config_path

    @classmethod
    def load(cls, path: str) -> ConfigManager:
        """Load and validate intersection config from a JSON file.

        Args:
            path: Filesystem path to the intersection JSON config file.

        Returns:
            A ConfigManager instance with the validated config.

        Raises:
            FileNotFoundError: If the config file does not exist.
            pydantic.ValidationError: If the config fails validation.
        """
        # TODO: Read JSON file, parse with IntersectionConfig, return ConfigManager
        raise NotImplementedError

    def validate(self) -> bool:
        """Re-validate the current config.

        Returns:
            True if valid, raises on invalid.
        """
        # TODO: Re-validate self.config using Pydantic
        raise NotImplementedError

    def reload(self) -> IntersectionConfig:
        """Reload the configuration from disk.

        Used when the cloud API pushes a config update.

        Returns:
            The newly loaded IntersectionConfig.
        """
        # TODO: Re-read the JSON file and update self.config
        raise NotImplementedError
