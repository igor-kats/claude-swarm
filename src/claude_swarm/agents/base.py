"""
Base agent definitions and types.
"""

import hashlib
import json
import re
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class AgentType(str, Enum):
    """Types of specialized agents available."""

    ORCHESTRATOR = "orchestrator"
    CODER = "coder"
    REVIEWER = "reviewer"
    SECURITY = "security"
    TESTER = "tester"
    DOCS = "docs"
    ARCHITECT = "architect"
    REFACTOR = "refactor"
    DEBUGGER = "debugger"
    # Mobile-specific
    MOBILE_UI = "mobile_ui"
    MOBILE_PERF = "mobile_perf"
    # Cloud-specific
    AWS = "aws"
    INFRA = "infra"


@dataclass
class AgentResult:
    """Result from an agent execution."""

    agent_type: AgentType
    task_id: str
    success: bool
    summary: str
    files_changed: list[str] = field(default_factory=list)
    files_created: list[str] = field(default_factory=list)
    issues_found: list[dict] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    blocked: bool = False
    block_reason: Optional[str] = None
    raw_output: Optional[str] = None
    execution_time: float = 0.0
    tokens_used: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "agent_type": self.agent_type.value,
            "task_id": self.task_id,
            "success": self.success,
            "summary": self.summary,
            "files_changed": self.files_changed,
            "files_created": self.files_created,
            "issues_found": self.issues_found,
            "suggestions": self.suggestions,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "execution_time": self.execution_time,
            "tokens_used": self.tokens_used,
        }

    def to_summary_string(self) -> str:
        """Convert to a compact summary string for orchestrator context."""
        parts = [f"[{self.agent_type.value.upper()}]"]
        parts.append("✓" if self.success else "✗")

        if self.files_changed:
            parts.append(f"Changed: {', '.join(self.files_changed[:3])}")
            if len(self.files_changed) > 3:
                parts.append(f"(+{len(self.files_changed) - 3} more)")

        if self.issues_found:
            critical = sum(1 for i in self.issues_found if i.get("severity") == "critical")
            warnings = sum(1 for i in self.issues_found if i.get("severity") == "warning")
            if critical:
                parts.append(f"🔴 {critical} critical")
            if warnings:
                parts.append(f"🟡 {warnings} warnings")

        if self.blocked:
            parts.append(f"⛔ BLOCKED: {self.block_reason}")

        return " | ".join(parts)


class BaseAgent(ABC):
    """Base class for all agents."""

    agent_type: AgentType
    system_prompt: str
    allowed_tools: list[str] = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
    max_turns: int = 10

    def __init__(
        self,
        project_root: Path,
        workspace: Path,
        config_override: Optional[dict] = None,
    ):
        self.project_root = project_root
        self.workspace = workspace
        self.config = config_override or {}

        # Apply config overrides (only if values are set)
        if self.config.get("system_prompt_override"):
            self.system_prompt = self.config["system_prompt_override"]
        if self.config.get("allowed_tools"):
            self.allowed_tools = self.config["allowed_tools"]
        if self.config.get("max_turns"):
            self.max_turns = self.config["max_turns"]

    def invoke(
        self,
        task: str,
        context_files: Optional[list[str]] = None,
        additional_context: Optional[str] = None,
    ) -> AgentResult:
        """
        Invoke the agent with a task.

        Spawns a fresh Claude Code instance with isolated context.
        """
        start_time = datetime.now()
        task_id = self._generate_task_id(task)

        # Build the full prompt
        prompt = self._build_prompt(task, context_files, additional_context)

        # Save task for debugging
        task_file = self.workspace / "tasks" / f"{self.agent_type.value}_{task_id}.md"
        task_file.parent.mkdir(parents=True, exist_ok=True)
        task_file.write_text(prompt)

        # Invoke Claude Code
        try:
            result = subprocess.run(
                [
                    "claude",
                    "--print",
                    "--output-format",
                    "json",
                    "--max-turns",
                    str(self.max_turns),
                    "--allowedTools",
                    ",".join(self.allowed_tools),
                    "--system-prompt",
                    self.system_prompt,
                    "-p",
                    prompt,
                ],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=300,  # 5 minute timeout per agent
            )

            output = result.stdout
            success = result.returncode == 0

        except subprocess.TimeoutExpired:
            output = "Agent timed out after 5 minutes"
            success = False
        except FileNotFoundError:
            output = "Claude CLI not found. Please install claude-code."
            success = False
        except Exception as e:
            output = f"Error invoking agent: {str(e)}"
            success = False

        execution_time = (datetime.now() - start_time).total_seconds()

        # Parse the output
        parsed = self._parse_output(output)

        # Save summary
        summary_file = self.workspace / "summaries" / f"{self.agent_type.value}_{task_id}.json"
        summary_file.parent.mkdir(parents=True, exist_ok=True)

        agent_result = AgentResult(
            agent_type=self.agent_type,
            task_id=task_id,
            success=success and not parsed.get("blocked", False),
            summary=parsed.get("summary", output[:1000]),
            files_changed=parsed.get("files_changed", []),
            files_created=parsed.get("files_created", []),
            issues_found=parsed.get("issues", []),
            suggestions=parsed.get("suggestions", []),
            blocked=parsed.get("blocked", False),
            block_reason=parsed.get("block_reason"),
            raw_output=output if not success else None,
            execution_time=execution_time,
        )

        summary_file.write_text(json.dumps(agent_result.to_dict(), indent=2))

        return agent_result

    def _build_prompt(
        self,
        task: str,
        context_files: Optional[list[str]] = None,
        additional_context: Optional[str] = None,
    ) -> str:
        """Build the full prompt for the agent."""
        parts = [f"# Task\n\n{task}"]

        if context_files:
            parts.append("\n\n# Relevant Files\n")
            for f in context_files:
                parts.append(f"- `{f}`")

        if additional_context:
            parts.append(f"\n\n# Additional Context\n\n{additional_context}")

        parts.append(f"\n\n# Output Requirements\n\n{self._get_output_format()}")

        return "\n".join(parts)

    @abstractmethod
    def _get_output_format(self) -> str:
        """Get the required output format for this agent type."""
        pass

    def _parse_output(self, output: str) -> dict:
        """Parse the agent's output to extract structured data."""
        result = {
            "summary": "",
            "files_changed": [],
            "files_created": [],
            "issues": [],
            "suggestions": [],
            "blocked": False,
            "block_reason": None,
        }

        # Try to extract JSON summary block
        json_match = re.search(r"```json\s*\n(\{.*?\})\s*\n```", output, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                result.update(parsed)
                return result
            except json.JSONDecodeError:
                pass

        # Try to extract summary block
        summary_match = re.search(r"```summary\s*\n(.*?)\n```", output, re.DOTALL)
        if summary_match:
            summary_text = summary_match.group(1)
            result["summary"] = summary_text

            # Parse key-value pairs from summary
            for line in summary_text.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip().lower().replace(" ", "_")
                    value = value.strip()

                    if key in ["files_changed", "files_created"]:
                        result[key] = [f.strip() for f in value.split(",") if f.strip()]
                    elif key == "blocked":
                        result["blocked"] = value.lower() in ["yes", "true", "1"]
                    elif key == "block_reason":
                        result["block_reason"] = value
        else:
            # Fallback: use last portion of output as summary
            result["summary"] = output[-1500:] if len(output) > 1500 else output

        return result

    def _generate_task_id(self, task: str) -> str:
        """Generate a unique task ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        hash_suffix = hashlib.md5(task.encode()).hexdigest()[:6]
        return f"{timestamp}_{hash_suffix}"
