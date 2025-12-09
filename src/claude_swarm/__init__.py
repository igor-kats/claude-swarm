"""
Claude Swarm - Universal Multi-Agent Orchestration for Claude Code

A system that spawns specialized AI agents (coder, reviewer, security, tester)
with isolated contexts, coordinated by a lightweight orchestrator.
"""

__version__ = "0.1.0"
__author__ = "Igor Kats"

from claude_swarm.orchestrator import Orchestrator
from claude_swarm.config import SwarmConfig, load_config
from claude_swarm.agents.base import AgentType

__all__ = [
    "Orchestrator",
    "SwarmConfig", 
    "load_config",
    "AgentType",
]
