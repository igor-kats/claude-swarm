"""
Agent registry for managing agent types and creation.
"""

from pathlib import Path
from typing import Optional, Type

from claude_swarm.agents.base import AgentType, BaseAgent
from claude_swarm.agents.specialized import (
    ArchitectAgent,
    AWSAgent,
    CoderAgent,
    DebuggerAgent,
    DocsAgent,
    MobileUIAgent,
    ReviewerAgent,
    SecurityAgent,
    TesterAgent,
)


class AgentRegistry:
    """Registry for managing agent types."""

    _agents: dict[AgentType, Type[BaseAgent]] = {
        AgentType.CODER: CoderAgent,
        AgentType.REVIEWER: ReviewerAgent,
        AgentType.SECURITY: SecurityAgent,
        AgentType.TESTER: TesterAgent,
        AgentType.DOCS: DocsAgent,
        AgentType.ARCHITECT: ArchitectAgent,
        AgentType.DEBUGGER: DebuggerAgent,
        AgentType.MOBILE_UI: MobileUIAgent,
        AgentType.AWS: AWSAgent,
    }

    @classmethod
    def register(cls, agent_type: AgentType, agent_class: Type[BaseAgent]):
        """Register a new agent type."""
        cls._agents[agent_type] = agent_class

    @classmethod
    def get(cls, agent_type: AgentType) -> Optional[Type[BaseAgent]]:
        """Get an agent class by type."""
        return cls._agents.get(agent_type)

    @classmethod
    def create(
        cls,
        agent_type: AgentType,
        project_root: Path,
        workspace: Path,
        config_override: Optional[dict] = None,
    ) -> BaseAgent:
        """Create an agent instance."""
        agent_class = cls.get(agent_type)
        if agent_class is None:
            raise ValueError(f"Unknown agent type: {agent_type}")

        return agent_class(
            project_root=project_root,
            workspace=workspace,
            config_override=config_override,
        )

    @classmethod
    def list_agents(cls) -> list[AgentType]:
        """List all registered agent types."""
        return list(cls._agents.keys())

    @classmethod
    def create_custom(
        cls,
        name: str,
        system_prompt: str,
        project_root: Path,
        workspace: Path,
        allowed_tools: Optional[list[str]] = None,
        max_turns: int = 10,
    ) -> BaseAgent:
        """Create a custom agent with a custom system prompt."""

        # Create a dynamic agent class
        class CustomAgent(BaseAgent):
            agent_type = AgentType.CODER  # Will be overridden

            def _get_output_format(self) -> str:
                return """After completing your task, output this EXACT format:

```json
{
  "summary": "Brief description of what was done",
  "files_changed": ["path/to/file"],
  "files_created": ["path/to/new_file"],
  "notes": "Any important information"
}
```"""

        agent = CustomAgent(
            project_root=project_root,
            workspace=workspace,
        )
        agent.system_prompt = system_prompt
        agent.allowed_tools = allowed_tools or ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
        agent.max_turns = max_turns

        return agent


def get_agent(
    agent_type: AgentType | str,
    project_root: Path,
    workspace: Path,
    config_override: Optional[dict] = None,
) -> BaseAgent:
    """
    Convenience function to get an agent instance.

    Args:
        agent_type: AgentType enum or string name
        project_root: Path to the project root
        workspace: Path to the swarm workspace (.swarm directory)
        config_override: Optional config overrides

    Returns:
        Configured agent instance
    """
    if isinstance(agent_type, str):
        agent_type = AgentType(agent_type)

    return AgentRegistry.create(
        agent_type=agent_type,
        project_root=project_root,
        workspace=workspace,
        config_override=config_override,
    )
