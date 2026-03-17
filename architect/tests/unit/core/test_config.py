"""Tests for ARCHITECT configuration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from architect.config import Settings


class TestSettingsDefaults:
    def test_default_values(self) -> None:
        with patch.dict("os.environ", {}, clear=False):
            s = Settings()
        assert s.max_cost_usd == 50.0
        assert s.max_total_iterations == 30
        assert s.max_sprint_iterations == 5
        assert s.workspace_path == Path("./workspace")
        assert s.vibe_path == Path("./.vibe")
        assert s.host == "0.0.0.0"
        assert s.port == 8080
        assert s.default_model == "claude-sonnet-4.6"
        assert s.log_format == "console"

    def test_api_keys_default_empty(self) -> None:
        s = Settings()
        assert s.openai_api_key.get_secret_value() == ""
        assert s.anthropic_api_key.get_secret_value() == ""


class TestSettingsEnvOverride:
    def test_override_budget(self) -> None:
        env = {
            "ARCHITECT_MAX_COST_USD": "100.0",
            "ARCHITECT_MAX_TOTAL_ITERATIONS": "50",
            "ARCHITECT_MAX_SPRINT_ITERATIONS": "10",
        }
        with patch.dict("os.environ", env, clear=False):
            s = Settings()
        assert s.max_cost_usd == 100.0
        assert s.max_total_iterations == 50
        assert s.max_sprint_iterations == 10

    def test_override_paths(self) -> None:
        env = {
            "ARCHITECT_WORKSPACE_PATH": "/custom/workspace",
            "ARCHITECT_VIBE_PATH": "/custom/vibe",
        }
        with patch.dict("os.environ", env, clear=False):
            s = Settings()
        assert s.workspace_path == Path("/custom/workspace")
        assert s.vibe_path == Path("/custom/vibe")

    def test_override_ui(self) -> None:
        env = {"ARCHITECT_HOST": "127.0.0.1", "ARCHITECT_PORT": "3000"}
        with patch.dict("os.environ", env, clear=False):
            s = Settings()
        assert s.host == "127.0.0.1"
        assert s.port == 3000

    def test_override_api_keys(self) -> None:
        env = {
            "ARCHITECT_OPENAI_API_KEY": "sk-test-openai",
            "ARCHITECT_ANTHROPIC_API_KEY": "sk-test-anthropic",
        }
        with patch.dict("os.environ", env, clear=False):
            s = Settings()
        assert s.openai_api_key.get_secret_value() == "sk-test-openai"
        assert s.anthropic_api_key.get_secret_value() == "sk-test-anthropic"

    def test_override_log_format(self) -> None:
        env = {"ARCHITECT_LOG_FORMAT": "json"}
        with patch.dict("os.environ", env, clear=False):
            s = Settings()
        assert s.log_format == "json"
