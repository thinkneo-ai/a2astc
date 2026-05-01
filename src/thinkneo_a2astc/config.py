"""
A2ASTC Configuration (Section 10.5).

Priority: constructor args > env vars (A2ASTC_*) > YAML file ($A2ASTC_CONFIG) > defaults.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger("a2astc.config")

# Default verdict bands: (lower_bound_inclusive, upper_bound_exclusive, verdict_name)
DEFAULT_VERDICT_BANDS: List[Tuple[float, float, str]] = [
    (0.00, 0.40, "ALLOW"),
    (0.40, 0.65, "WARN"),
    (0.65, 0.80, "THROTTLE"),
    (0.80, 0.92, "ISOLATE"),
    (0.92, 1.01, "TERMINATE"),  # 1.01 to include 1.0
]

DEFAULT_AUDIT_WEIGHTS: Dict[str, float] = {
    "topology": 0.2,
    "semantic": 0.2,
    "privilege": 0.2,
    "sidechannel": 0.2,
    "cascade": 0.2,
}

DEFAULT_ESCALATION_PAIRS: List[Tuple[frozenset, str]] = [
    (frozenset({"read-untrusted", "write-trusted"}), "RESTRICTED"),
    (frozenset({"code-exec", "net-egress"}), "RESTRICTED"),
    (frozenset({"memory-write", "identity-assumption"}), "RESTRICTED"),
]

# If any 3 of these 4 categories are present, classify as HIGH_RISK
HIGH_RISK_CATEGORIES: List[str] = [
    "read-untrusted",
    "code-exec",
    "memory-write",
    "identity-assumption",
]


@dataclass
class A2ASTCConfig:
    """Central configuration for the A2ASTC compliance layer.

    Configuration is resolved with the following priority:
    1. Constructor arguments (highest)
    2. Environment variables with A2ASTC_ prefix
    3. YAML file pointed to by $A2ASTC_CONFIG
    4. Built-in defaults (lowest)
    """

    # Team detection
    team_window: float = 600.0  # seconds
    min_team_size: int = 2

    # Verdict bands
    verdict_bands: List[Tuple[float, float, str]] = field(
        default_factory=lambda: list(DEFAULT_VERDICT_BANDS)
    )

    # Throttle parameters
    throttle_bucket_capacity: float = 10.0
    throttle_bucket_refill_rate: float = 1.0  # tokens per second

    # Cooldown for reversible interventions
    cooldown_interval: float = 60.0  # seconds

    # Audit signal weights
    audit_weights: Dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_AUDIT_WEIGHTS)
    )

    # Trail retention
    trail_retention_days: int = 365

    # Escalation pairs
    escalation_pairs: List[Tuple[frozenset, str]] = field(
        default_factory=lambda: list(DEFAULT_ESCALATION_PAIRS)
    )
    high_risk_categories: List[str] = field(
        default_factory=lambda: list(HIGH_RISK_CATEGORIES)
    )
    high_risk_threshold: int = 3  # how many of the 4 categories to trigger HIGH_RISK

    # Terminate deadline
    terminate_deadline: float = 1.0  # seconds to block all edges

    # Logging
    log_level: str = "INFO"

    @classmethod
    def from_yaml(cls, path: str | Path) -> "A2ASTCConfig":
        """Load configuration from a YAML file."""
        path = Path(path)
        if not path.exists():
            logger.warning("Config file %s not found, using defaults", path)
            return cls()

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "A2ASTCConfig":
        """Create config from a dictionary."""
        kwargs: Dict[str, Any] = {}

        if "team_window" in data:
            kwargs["team_window"] = float(data["team_window"])
        if "min_team_size" in data:
            kwargs["min_team_size"] = int(data["min_team_size"])
        if "verdict_bands" in data:
            kwargs["verdict_bands"] = [
                (float(b[0]), float(b[1]), str(b[2])) for b in data["verdict_bands"]
            ]
        if "throttle_bucket_capacity" in data:
            kwargs["throttle_bucket_capacity"] = float(data["throttle_bucket_capacity"])
        if "throttle_bucket_refill_rate" in data:
            kwargs["throttle_bucket_refill_rate"] = float(
                data["throttle_bucket_refill_rate"]
            )
        if "cooldown_interval" in data:
            kwargs["cooldown_interval"] = float(data["cooldown_interval"])
        if "audit_weights" in data:
            kwargs["audit_weights"] = {
                str(k): float(v) for k, v in data["audit_weights"].items()
            }
        if "trail_retention_days" in data:
            kwargs["trail_retention_days"] = int(data["trail_retention_days"])
        if "terminate_deadline" in data:
            kwargs["terminate_deadline"] = float(data["terminate_deadline"])
        if "log_level" in data:
            kwargs["log_level"] = str(data["log_level"])

        return cls(**kwargs)

    @classmethod
    def resolve(
        cls,
        constructor_args: Optional[Dict[str, Any]] = None,
    ) -> "A2ASTCConfig":
        """Resolve configuration with full priority chain.

        Priority: constructor_args > env vars > YAML file > defaults.
        """
        # Start with defaults
        config_dict: Dict[str, Any] = {}

        # Layer 1: YAML file (lowest after defaults)
        yaml_path = os.environ.get("A2ASTC_CONFIG")
        if yaml_path:
            yaml_file = Path(yaml_path)
            if yaml_file.exists():
                with open(yaml_file, "r", encoding="utf-8") as f:
                    yaml_data = yaml.safe_load(f) or {}
                config_dict.update(yaml_data)
                logger.info("Loaded config from YAML: %s", yaml_path)
            else:
                logger.warning("A2ASTC_CONFIG=%s not found", yaml_path)

        # Layer 2: Environment variables
        env_mapping: Dict[str, str] = {
            "A2ASTC_TEAM_WINDOW": "team_window",
            "A2ASTC_MIN_TEAM_SIZE": "min_team_size",
            "A2ASTC_THROTTLE_BUCKET_CAPACITY": "throttle_bucket_capacity",
            "A2ASTC_THROTTLE_BUCKET_REFILL_RATE": "throttle_bucket_refill_rate",
            "A2ASTC_COOLDOWN_INTERVAL": "cooldown_interval",
            "A2ASTC_TRAIL_RETENTION_DAYS": "trail_retention_days",
            "A2ASTC_TERMINATE_DEADLINE": "terminate_deadline",
            "A2ASTC_LOG_LEVEL": "log_level",
        }

        for env_var, config_key in env_mapping.items():
            value = os.environ.get(env_var)
            if value is not None:
                config_dict[config_key] = value
                logger.info("Config from env: %s=%s", env_var, value)

        # Layer 3: Constructor arguments (highest priority)
        if constructor_args:
            config_dict.update(constructor_args)

        # Log defaults that will be used
        instance = cls._from_dict(config_dict) if config_dict else cls()
        _log_defaults(instance, config_dict)

        return instance


def _log_defaults(config: A2ASTCConfig, overrides: Dict[str, Any]) -> None:
    """Log which configuration values are using defaults."""
    default_config = A2ASTCConfig()
    default_fields = {
        "team_window",
        "min_team_size",
        "throttle_bucket_capacity",
        "throttle_bucket_refill_rate",
        "cooldown_interval",
        "trail_retention_days",
        "terminate_deadline",
        "log_level",
    }

    for field_name in default_fields:
        if field_name not in overrides:
            value = getattr(default_config, field_name)
            logger.info("Using default for %s: %s", field_name, value)
