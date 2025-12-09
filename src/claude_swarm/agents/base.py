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
    max_turns: int = 30

    def __init__(
        self,
        project_root: Path,
        workspace: Path,
        config_override: Optional[dict] = None,
        verbose: bool = False,
        interactive: bool = False,
    ):
        self.project_root = project_root
        self.workspace = workspace
        self.config = config_override or {}
        self.verbose = verbose
        self.interactive = interactive

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

        if self.verbose:
            print(f"\n{'='*60}")
            print(f"🤖 Agent: {self.agent_type.value.upper()}")
            print(f"📝 Task ID: {task_id}")
            print(f"🔧 Max turns: {self.max_turns}")
            print(f"🛠️  Tools: {', '.join(self.allowed_tools)}")
            print(f"📁 Working dir: {self.project_root}")
            print(f"{'='*60}\n")

        if self.interactive:
            # Run in a new terminal tab
            output, success = self._invoke_interactive(prompt, task_id)
        else:
            # Run in background with captured output
            output, success = self._invoke_background(prompt)

        execution_time = (datetime.now() - start_time).total_seconds()

        if self.verbose:
            print(f"\n{'='*60}")
            print(f"✅ Agent {self.agent_type.value} completed in {execution_time:.1f}s")
            print(f"{'='*60}\n")

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

    def _invoke_background(self, prompt: str) -> tuple[str, bool]:
        """Invoke Claude Code in background with captured output."""
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
                timeout=600,  # 10 minute timeout per agent
            )

            return result.stdout, result.returncode == 0

        except subprocess.TimeoutExpired:
            return "Agent timed out after 10 minutes", False
        except FileNotFoundError:
            return "Claude CLI not found. Please install claude-code.", False
        except Exception as e:
            return f"Error invoking agent: {str(e)}", False

    def _invoke_interactive(self, prompt: str, task_id: str) -> tuple[str, bool]:
        """Invoke Claude Code in a new terminal tab for interactive viewing."""
        import os
        import platform
        import stat
        import time

        # Save prompt to a file
        prompt_file = self.workspace / "tasks" / f"{self.agent_type.value}_{task_id}_prompt.txt"
        prompt_file.write_text(prompt)

        # Save system prompt to a file (to avoid shell escaping issues)
        system_prompt_file = (
            self.workspace / "tasks" / f"{self.agent_type.value}_{task_id}_system.txt"
        )
        system_prompt_file.write_text(self.system_prompt)

        # Create a shell script to run the agent (avoids escaping issues)
        script_file = self.workspace / "tasks" / f"{self.agent_type.value}_{task_id}_run.sh"
        script_content = f"""#!/bin/bash
cd "{self.project_root}"
echo "🤖 Running {self.agent_type.value} agent..."
echo "📁 Working directory: $(pwd)"
echo "🔧 Max turns: {self.max_turns}"
echo ""
echo "{'='*60}"
echo ""

claude \\
    --max-turns {self.max_turns} \\
    --allowedTools "{','.join(self.allowed_tools)}" \\
    --system-prompt "$(cat "{system_prompt_file}")" \\
    -p "$(cat "{prompt_file}")"

echo ""
echo "{'='*60}"
echo "✅ Agent {self.agent_type.value} completed."
echo "Press any key to close..."
read -n 1
"""
        script_file.write_text(script_content)
        # Make executable
        os.chmod(script_file, os.stat(script_file).st_mode | stat.S_IEXEC)

        system = platform.system()

        try:
            if system == "Darwin":  # macOS
                # Open a new Terminal tab running the script
                apple_script = f"""
                tell application "Terminal"
                    activate
                    do script "{script_file}"
                end tell
                """
                subprocess.run(["osascript", "-e", apple_script], check=True)

            elif system == "Linux":
                # Try common terminal emulators
                terminals = [
                    ["gnome-terminal", "--", "bash"],
                    ["xterm", "-e", "bash"],
                    ["konsole", "-e", "bash"],
                ]
                for term_cmd in terminals:
                    try:
                        subprocess.Popen(
                            term_cmd + [str(script_file)],
                            start_new_session=True,
                        )
                        break
                    except FileNotFoundError:
                        continue
                else:
                    # Fallback to background execution
                    print("⚠️  No terminal emulator found, running in background...")
                    return self._invoke_background(prompt)

            else:
                # Windows or unknown - fall back to background
                print(f"⚠️  Interactive mode not supported on {system}, running in background...")
                return self._invoke_background(prompt)

            # In interactive mode, we don't capture output - user watches in terminal
            # Just wait a moment and return success
            print(f"🖥️  Agent {self.agent_type.value} launched in new terminal window")
            print("   Watch the terminal for live output")
            time.sleep(2)

            # Return a placeholder - the user will see real output in the terminal
            return (
                json.dumps(
                    {
                        "type": "result",
                        "subtype": "interactive",
                        "message": f"Agent {self.agent_type.value} running in separate terminal",
                    }
                ),
                True,
            )

        except Exception as e:
            return f"Error launching interactive terminal: {str(e)}", False

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

        # First, try to parse as raw JSON (Claude CLI output format)
        try:
            raw_json = json.loads(output)
            if isinstance(raw_json, dict) and raw_json.get("type") == "result":
                # This is Claude CLI's JSON output format
                subtype = raw_json.get("subtype", "")
                if subtype == "error_max_turns":
                    result["summary"] = "Agent reached maximum turns limit"
                    result["blocked"] = True
                    result["block_reason"] = "Max turns reached - task may be too complex"
                elif subtype == "error":
                    result["summary"] = f"Agent error: {raw_json.get('error', 'Unknown error')}"
                    result["blocked"] = True
                    result["block_reason"] = raw_json.get("error", "Unknown error")
                elif subtype == "interactive":
                    # Interactive mode - agent running in separate terminal
                    result["summary"] = raw_json.get("message", "Running in separate terminal")
                else:
                    # Success case - extract result text if available
                    result["summary"] = raw_json.get("result", "Task completed")
                return result
        except (json.JSONDecodeError, TypeError):
            pass

        # Try to extract JSON summary block from markdown
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
