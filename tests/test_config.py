"""Tests for A2ASTCConfig (Section 10.5)."""

import os
import tempfile
import pytest
import yaml
from thinkneo_a2astc.config import A2ASTCConfig


class TestConfigDefaults:
    """Tests for default configuration values."""

    def test_default_team_window(self):
        """Default team window should be 600s."""
        cfg = A2ASTCConfig()
        assert cfg.team_window == 600.0

    def test_default_cooldown(self):
        """Default cooldown should be 60s."""
        cfg = A2ASTCConfig()
        assert cfg.cooldown_interval == 60.0

    def test_default_trail_retention(self):
        """Default retention should be 365 days."""
        cfg = A2ASTCConfig()
        assert cfg.trail_retention_days == 365

    def test_default_verdict_bands(self):
        """Should have 5 default verdict bands."""
        cfg = A2ASTCConfig()
        assert len(cfg.verdict_bands) == 5

    def test_default_audit_weights(self):
        """Should have 5 audit weights summing to 1.0."""
        cfg = A2ASTCConfig()
        assert len(cfg.audit_weights) == 5
        assert abs(sum(cfg.audit_weights.values()) - 1.0) < 0.001


class TestConfigYAML:
    """Tests for YAML configuration loading."""

    def test_load_yaml(self):
        """Should load config from YAML file."""
        data = {"team_window": 300.0, "cooldown_interval": 30.0}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(data, f)
            f.flush()
            cfg = A2ASTCConfig.from_yaml(f.name)
        assert cfg.team_window == 300.0
        assert cfg.cooldown_interval == 30.0
        os.unlink(f.name)

    def test_missing_yaml_uses_defaults(self):
        """Missing YAML should use defaults."""
        cfg = A2ASTCConfig.from_yaml("/nonexistent/path.yaml")
        assert cfg.team_window == 600.0

    def test_partial_yaml(self):
        """Partial YAML should fill with defaults."""
        data = {"team_window": 120.0}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(data, f)
            f.flush()
            cfg = A2ASTCConfig.from_yaml(f.name)
        assert cfg.team_window == 120.0
        assert cfg.cooldown_interval == 60.0  # Default
        os.unlink(f.name)


class TestConfigEnvVars:
    """Tests for environment variable configuration."""

    def test_env_var_override(self):
        """Environment variables should override defaults."""
        os.environ["A2ASTC_TEAM_WINDOW"] = "200.0"
        os.environ["A2ASTC_COOLDOWN_INTERVAL"] = "30.0"
        try:
            cfg = A2ASTCConfig.resolve()
            assert cfg.team_window == 200.0
            assert cfg.cooldown_interval == 30.0
        finally:
            del os.environ["A2ASTC_TEAM_WINDOW"]
            del os.environ["A2ASTC_COOLDOWN_INTERVAL"]

    def test_env_var_with_yaml(self):
        """Env vars should override YAML."""
        data = {"team_window": 300.0}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(data, f)
            f.flush()
            os.environ["A2ASTC_CONFIG"] = f.name
            os.environ["A2ASTC_TEAM_WINDOW"] = "100.0"
            try:
                cfg = A2ASTCConfig.resolve()
                assert cfg.team_window == 100.0  # Env wins over YAML
            finally:
                del os.environ["A2ASTC_CONFIG"]
                del os.environ["A2ASTC_TEAM_WINDOW"]
                os.unlink(f.name)


class TestConfigPriority:
    """Tests for configuration priority resolution."""

    def test_constructor_wins_over_env(self):
        """Constructor args should override env vars."""
        os.environ["A2ASTC_TEAM_WINDOW"] = "200.0"
        try:
            cfg = A2ASTCConfig.resolve(constructor_args={"team_window": 50.0})
            assert cfg.team_window == 50.0
        finally:
            del os.environ["A2ASTC_TEAM_WINDOW"]

    def test_full_priority_chain(self):
        """Full priority: constructor > env > YAML > default."""
        data = {"team_window": 300.0, "cooldown_interval": 30.0}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(data, f)
            f.flush()
            os.environ["A2ASTC_CONFIG"] = f.name
            os.environ["A2ASTC_COOLDOWN_INTERVAL"] = "20.0"
            try:
                cfg = A2ASTCConfig.resolve(
                    constructor_args={"team_window": 10.0}
                )
                assert cfg.team_window == 10.0  # Constructor
                assert cfg.cooldown_interval == 20.0  # Env beats YAML
            finally:
                del os.environ["A2ASTC_CONFIG"]
                del os.environ["A2ASTC_COOLDOWN_INTERVAL"]
                os.unlink(f.name)
