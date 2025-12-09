"""Tests for agent module."""

from pathlib import Path

import pytest

from claude_swarm.agents.base import AgentType, AgentResult, BaseAgent
from claude_swarm.agents.registry import AgentRegistry
from claude_swarm.agents.specialized import (
    CoderAgent,
    ReviewerAgent,
    SecurityAgent,
    TesterAgent,
)


class TestAgentType:
    """Tests for AgentType enum."""

    def test_agent_types_exist(self):
        """Test that expected agent types exist."""
        assert AgentType.CODER.value == "coder"
        assert AgentType.REVIEWER.value == "reviewer"
        assert AgentType.SECURITY.value == "security"
        assert AgentType.TESTER.value == "tester"
        assert AgentType.ARCHITECT.value == "architect"
        assert AgentType.DEBUGGER.value == "debugger"

    def test_agent_type_from_string(self):
        """Test creating AgentType from string."""
        assert AgentType("coder") == AgentType.CODER
        assert AgentType("security") == AgentType.SECURITY


class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_result_to_dict(self):
        """Test serialization of AgentResult."""
        result = AgentResult(
            agent_type=AgentType.CODER,
            task_id="test_123",
            success=True,
            summary="Test completed",
            files_changed=["file1.py"],
        )
        d = result.to_dict()

        assert d["agent_type"] == "coder"
        assert d["task_id"] == "test_123"
        assert d["success"] is True
        assert d["files_changed"] == ["file1.py"]

    def test_result_to_summary_string(self):
        """Test summary string generation."""
        result = AgentResult(
            agent_type=AgentType.REVIEWER,
            task_id="test_456",
            success=True,
            summary="Review complete",
            files_changed=["a.py", "b.py"],
        )
        summary = result.to_summary_string()

        assert "[REVIEWER]" in summary
        assert "a.py" in summary

    def test_blocked_result_summary(self):
        """Test summary string for blocked result."""
        result = AgentResult(
            agent_type=AgentType.SECURITY,
            task_id="test_789",
            success=False,
            summary="Security issues found",
            blocked=True,
            block_reason="SQL injection vulnerability",
        )
        summary = result.to_summary_string()

        assert "BLOCKED" in summary
        assert "SQL injection" in summary


class TestAgentRegistry:
    """Tests for AgentRegistry."""

    def test_get_registered_agent(self):
        """Test getting a registered agent class."""
        agent_class = AgentRegistry.get(AgentType.CODER)
        assert agent_class == CoderAgent

    def test_get_unknown_agent(self):
        """Test getting an unknown agent type returns None."""
        # Create a fake enum value for testing
        result = AgentRegistry.get(AgentType.ORCHESTRATOR)
        assert result is None

    def test_list_agents(self):
        """Test listing all registered agents."""
        agents = AgentRegistry.list_agents()
        assert AgentType.CODER in agents
        assert AgentType.REVIEWER in agents
        assert AgentType.SECURITY in agents

    def test_create_agent(self, tmp_path):
        """Test creating an agent instance."""
        workspace = tmp_path / ".swarm"
        workspace.mkdir()

        agent = AgentRegistry.create(
            agent_type=AgentType.CODER,
            project_root=tmp_path,
            workspace=workspace,
        )

        assert isinstance(agent, CoderAgent)
        assert agent.project_root == tmp_path
        assert agent.workspace == workspace


class TestSpecializedAgents:
    """Tests for specialized agent classes."""

    @pytest.fixture
    def agent_setup(self, tmp_path):
        """Setup common agent test fixtures."""
        workspace = tmp_path / ".swarm"
        workspace.mkdir()
        (workspace / "tasks").mkdir()
        (workspace / "summaries").mkdir()
        return tmp_path, workspace

    def test_coder_agent_attributes(self, agent_setup):
        """Test CoderAgent has correct attributes."""
        project_root, workspace = agent_setup
        agent = CoderAgent(project_root=project_root, workspace=workspace)

        assert agent.agent_type == AgentType.CODER
        assert "Write" in agent.allowed_tools
        assert "Edit" in agent.allowed_tools
        assert agent.max_turns == 15

    def test_reviewer_agent_read_only(self, agent_setup):
        """Test ReviewerAgent has read-only tools."""
        project_root, workspace = agent_setup
        agent = ReviewerAgent(project_root=project_root, workspace=workspace)

        assert agent.agent_type == AgentType.REVIEWER
        assert "Read" in agent.allowed_tools
        assert "Write" not in agent.allowed_tools
        assert "Edit" not in agent.allowed_tools

    def test_security_agent_attributes(self, agent_setup):
        """Test SecurityAgent has correct attributes."""
        project_root, workspace = agent_setup
        agent = SecurityAgent(project_root=project_root, workspace=workspace)

        assert agent.agent_type == AgentType.SECURITY
        assert "Bash" in agent.allowed_tools  # For grep patterns

    def test_agent_config_override(self, agent_setup):
        """Test that config overrides are applied correctly."""
        project_root, workspace = agent_setup

        # Test that None values don't override defaults
        agent = CoderAgent(
            project_root=project_root,
            workspace=workspace,
            config_override={
                "system_prompt_override": None,
                "allowed_tools": [],
                "max_turns": 20,
            },
        )

        # system_prompt should NOT be overridden (value was None)
        assert agent.system_prompt is not None
        assert "CODE WRITER" in agent.system_prompt

        # allowed_tools should NOT be overridden (value was empty)
        assert len(agent.allowed_tools) > 0

        # max_turns SHOULD be overridden (value was truthy)
        assert agent.max_turns == 20

    def test_agent_with_custom_system_prompt(self, agent_setup):
        """Test agent with custom system prompt override."""
        project_root, workspace = agent_setup

        agent = CoderAgent(
            project_root=project_root,
            workspace=workspace,
            config_override={
                "system_prompt_override": "Custom prompt for testing",
            },
        )

        assert agent.system_prompt == "Custom prompt for testing"


class TestAgentPromptBuilding:
    """Tests for agent prompt building."""

    @pytest.fixture
    def coder_agent(self, tmp_path):
        """Create a coder agent for testing."""
        workspace = tmp_path / ".swarm"
        workspace.mkdir()
        (workspace / "tasks").mkdir()
        return CoderAgent(project_root=tmp_path, workspace=workspace)

    def test_build_basic_prompt(self, coder_agent):
        """Test basic prompt building."""
        prompt = coder_agent._build_prompt("Write a hello world function")

        assert "# Task" in prompt
        assert "hello world" in prompt
        assert "# Output Requirements" in prompt

    def test_build_prompt_with_files(self, coder_agent):
        """Test prompt building with context files."""
        prompt = coder_agent._build_prompt(
            "Update the function",
            context_files=["src/main.py", "src/utils.py"],
        )

        assert "# Relevant Files" in prompt
        assert "src/main.py" in prompt
        assert "src/utils.py" in prompt

    def test_build_prompt_with_context(self, coder_agent):
        """Test prompt building with additional context."""
        prompt = coder_agent._build_prompt(
            "Fix the bug",
            additional_context="Previous agent found an issue in line 42",
        )

        assert "# Additional Context" in prompt
        assert "line 42" in prompt
