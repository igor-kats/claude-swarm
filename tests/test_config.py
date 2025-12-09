"""Tests for configuration module."""

import tempfile
from pathlib import Path

import pytest

from claude_swarm.config import (
    ProjectType,
    SwarmConfig,
    AgentConfig,
    detect_project_type,
    load_config,
    init_config,
)


class TestProjectTypeDetection:
    """Tests for project type auto-detection."""

    def test_detect_python_pyproject(self, tmp_path):
        """Detect Python project from pyproject.toml."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        assert detect_project_type(tmp_path) == ProjectType.PYTHON

    def test_detect_python_requirements(self, tmp_path):
        """Detect Python project from requirements.txt."""
        (tmp_path / "requirements.txt").write_text("click>=8.0\n")
        assert detect_project_type(tmp_path) == ProjectType.PYTHON

    def test_detect_react_native(self, tmp_path):
        """Detect React Native project from package.json."""
        (tmp_path / "package.json").write_text('{"dependencies": {"react-native": "0.72.0"}}')
        assert detect_project_type(tmp_path) == ProjectType.REACT_NATIVE

    def test_detect_nodejs(self, tmp_path):
        """Detect Node.js project from package.json (without react-native)."""
        (tmp_path / "package.json").write_text('{"dependencies": {"express": "4.18.0"}}')
        assert detect_project_type(tmp_path) == ProjectType.NODEJS

    def test_detect_typescript(self, tmp_path):
        """Detect TypeScript project from tsconfig.json."""
        (tmp_path / "tsconfig.json").write_text('{"compilerOptions": {}}')
        assert detect_project_type(tmp_path) == ProjectType.TYPESCRIPT

    def test_detect_rust(self, tmp_path):
        """Detect Rust project from Cargo.toml."""
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"\n')
        assert detect_project_type(tmp_path) == ProjectType.RUST

    def test_detect_go(self, tmp_path):
        """Detect Go project from go.mod."""
        (tmp_path / "go.mod").write_text("module example.com/test\n")
        assert detect_project_type(tmp_path) == ProjectType.GO

    def test_detect_generic_fallback(self, tmp_path):
        """Fall back to generic when no known project files."""
        assert detect_project_type(tmp_path) == ProjectType.GENERIC


class TestSwarmConfig:
    """Tests for SwarmConfig model."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SwarmConfig()
        assert config.project_type == ProjectType.GENERIC
        assert config.workspace_dir == ".swarm"
        assert config.orchestrator.auto_pipeline is True
        assert config.orchestrator.require_tests is True

    def test_config_with_agents(self):
        """Test configuration with custom agent settings."""
        config = SwarmConfig(
            agents={
                "coder": AgentConfig(max_turns=20, enabled=True),
                "tester": AgentConfig(enabled=False),
            }
        )
        assert config.agents["coder"].max_turns == 20
        assert config.agents["coder"].enabled is True
        assert config.agents["tester"].enabled is False


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_default_config(self, tmp_path):
        """Load config when no .swarm.yaml exists."""
        config = load_config(tmp_path)
        assert config.project_type == ProjectType.GENERIC
        assert config.project_root == tmp_path

    def test_load_config_with_yaml(self, tmp_path):
        """Load config from .swarm.yaml file."""
        yaml_content = """
project_type: python
workspace_dir: .swarm
orchestrator:
  max_context_tokens: 10000
  require_tests: false
agents:
  coder:
    enabled: true
    max_turns: 25
"""
        (tmp_path / ".swarm.yaml").write_text(yaml_content)
        config = load_config(tmp_path)

        assert config.project_type == ProjectType.PYTHON
        assert config.orchestrator.max_context_tokens == 10000
        assert config.orchestrator.require_tests is False
        assert config.agents["coder"].max_turns == 25


class TestInitConfig:
    """Tests for init_config function."""

    def test_init_creates_config_file(self, tmp_path):
        """Test that init_config creates .swarm.yaml."""
        config_path = init_config(tmp_path)

        assert config_path.exists()
        assert config_path.name == ".swarm.yaml"

    def test_init_creates_workspace(self, tmp_path):
        """Test that init_config creates workspace directory."""
        init_config(tmp_path)

        workspace = tmp_path / ".swarm"
        assert workspace.exists()
        assert (workspace / "summaries").exists()
        assert (workspace / "tasks").exists()
        assert (workspace / "state").exists()

    def test_init_fails_if_exists(self, tmp_path):
        """Test that init_config fails if config already exists."""
        (tmp_path / ".swarm.yaml").write_text("existing config")

        with pytest.raises(FileExistsError):
            init_config(tmp_path)

    def test_init_force_overwrites(self, tmp_path):
        """Test that init_config with force=True overwrites existing."""
        (tmp_path / ".swarm.yaml").write_text("old config")

        config_path = init_config(tmp_path, force=True)
        content = config_path.read_text()

        assert "old config" not in content
        assert "project_type:" in content
