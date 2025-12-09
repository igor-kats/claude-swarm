"""
Main orchestrator for the Claude Swarm.
Coordinates agents, manages state, and maintains minimal context.
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from claude_swarm.agents.base import AgentResult, AgentType
from claude_swarm.agents.registry import AgentRegistry
from claude_swarm.config import SwarmConfig, load_config


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class Task:
    """A task to be executed by an agent."""

    id: str
    agent_type: AgentType
    description: str
    context_files: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[AgentResult] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_type": self.agent_type.value,
            "description": self.description,
            "context_files": self.context_files,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "result": self.result.to_dict() if self.result else None,
        }


@dataclass
class SwarmState:
    """State of the swarm for a feature/session."""

    session_id: str
    feature_description: str
    created_at: str
    updated_at: str
    status: str = "active"
    architecture: Optional[str] = None
    tasks: list[Task] = field(default_factory=list)
    completed_summaries: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "feature_description": self.feature_description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "architecture": self.architecture,
            "tasks": [t.to_dict() for t in self.tasks],
            "completed_summaries": self.completed_summaries,
            "blockers": self.blockers,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SwarmState":
        tasks = []
        for t in data.get("tasks", []):
            task = Task(
                id=t["id"],
                agent_type=AgentType(t["agent_type"]),
                description=t["description"],
                context_files=t.get("context_files", []),
                depends_on=t.get("depends_on", []),
                status=TaskStatus(t["status"]),
            )
            tasks.append(task)

        return cls(
            session_id=data["session_id"],
            feature_description=data["feature_description"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            status=data.get("status", "active"),
            architecture=data.get("architecture"),
            tasks=tasks,
            completed_summaries=data.get("completed_summaries", []),
            blockers=data.get("blockers", []),
        )


class Orchestrator:
    """
    Main orchestrator for the Claude Swarm.

    Manages a pool of specialized agents, routes tasks,
    and maintains a lightweight context with only summaries.
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        config: Optional[SwarmConfig] = None,
    ):
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self.config = config or load_config(self.project_root)

        # Setup workspace
        self.workspace = self.project_root / self.config.workspace_dir
        self.workspace.mkdir(exist_ok=True)
        (self.workspace / "summaries").mkdir(exist_ok=True)
        (self.workspace / "tasks").mkdir(exist_ok=True)
        (self.workspace / "state").mkdir(exist_ok=True)

        # Current session state
        self.state: Optional[SwarmState] = None

        # Task counter for ID generation
        self._task_counter = 0

    def _generate_task_id(self) -> str:
        """Generate a unique task ID."""
        self._task_counter += 1
        return f"task_{self._task_counter:03d}"

    def _save_state(self):
        """Save current state to disk."""
        if self.state:
            state_file = self.workspace / "state" / f"{self.state.session_id}.json"
            self.state.updated_at = datetime.now().isoformat()
            state_file.write_text(json.dumps(self.state.to_dict(), indent=2))

    def _load_state(self, session_id: str) -> Optional[SwarmState]:
        """Load state from disk."""
        state_file = self.workspace / "state" / f"{session_id}.json"
        if state_file.exists():
            data = json.loads(state_file.read_text())
            return SwarmState.from_dict(data)
        return None

    def start_session(self, feature_description: str) -> str:
        """
        Start a new development session for a feature.

        Returns the session ID.
        """
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.state = SwarmState(
            session_id=session_id,
            feature_description=feature_description,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )

        self._save_state()
        return session_id

    def resume_session(self, session_id: str) -> bool:
        """Resume an existing session."""
        state = self._load_state(session_id)
        if state:
            self.state = state
            return True
        return False

    def list_sessions(self) -> list[dict]:
        """List all available sessions."""
        sessions = []
        state_dir = self.workspace / "state"

        for state_file in state_dir.glob("*.json"):
            try:
                data = json.loads(state_file.read_text())
                sessions.append(
                    {
                        "session_id": data["session_id"],
                        "feature": data["feature_description"][:50],
                        "status": data.get("status", "unknown"),
                        "updated": data["updated_at"],
                    }
                )
            except Exception:
                continue

        return sorted(sessions, key=lambda x: x["updated"], reverse=True)

    def invoke_agent(
        self,
        agent_type: AgentType,
        task: str,
        context_files: Optional[list[str]] = None,
        additional_context: Optional[str] = None,
    ) -> AgentResult:
        """
        Invoke a single agent with a task.

        This spawns a fresh Claude Code instance with isolated context.
        """
        # Get agent config overrides from swarm config
        agent_config = {}
        if agent_type.value in self.config.agents:
            agent_config = self.config.agents[agent_type.value].model_dump()

        # Create agent instance
        agent = AgentRegistry.create(
            agent_type=agent_type,
            project_root=self.project_root,
            workspace=self.workspace,
            config_override=agent_config,
        )

        # Build additional context from recent summaries
        if self.state and self.state.completed_summaries:
            recent_context = "\n".join(self.state.completed_summaries[-5:])  # Last 5 summaries
            if additional_context:
                additional_context = f"{additional_context}\n\n## Recent Activity\n{recent_context}"
            else:
                additional_context = f"## Recent Activity\n{recent_context}"

        # Invoke the agent
        result = agent.invoke(
            task=task,
            context_files=context_files,
            additional_context=additional_context,
        )

        # Store summary in state (compressed)
        if self.state:
            summary_line = result.to_summary_string()
            self.state.completed_summaries.append(summary_line)

            # Keep only last 20 summaries to manage context
            if len(self.state.completed_summaries) > 20:
                self.state.completed_summaries = self.state.completed_summaries[-20:]

            if result.blocked:
                self.state.blockers.append(f"{agent_type.value}: {result.block_reason}")

            self._save_state()

        return result

    def run_pipeline(
        self,
        task: str,
        context_files: Optional[list[str]] = None,
        skip_security: bool = False,
        skip_tests: bool = False,
        skip_review: bool = False,
    ) -> dict[str, AgentResult]:
        """
        Run a full development pipeline for a code change.

        Pipeline: Coder → (Security + Review in parallel) → Tester
        """
        results = {}

        # 1. Code implementation
        print("🔨 Running coder agent...")
        code_result = self.invoke_agent(
            AgentType.CODER,
            task,
            context_files=context_files,
        )
        results["coder"] = code_result

        if not code_result.success:
            print("❌ Coder failed")
            return results

        # Get files that were changed for review
        changed_files = code_result.files_changed + code_result.files_created
        code_summary = code_result.summary

        # 2. Parallel security and code review
        review_tasks = []

        security_config = self.config.agents.get("security")
        if not skip_security and (security_config is None or security_config.enabled):
            review_tasks.append(("security", AgentType.SECURITY))

        reviewer_config = self.config.agents.get("reviewer")
        if not skip_review and (reviewer_config is None or reviewer_config.enabled):
            review_tasks.append(("review", AgentType.REVIEWER))

        if review_tasks and self.config.orchestrator.parallel_reviews:
            print("🔍 Running security and review agents in parallel...")
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {}
                for name, agent_type in review_tasks:
                    future = executor.submit(
                        self.invoke_agent,
                        agent_type,
                        f"Review these changes:\n{code_summary}",
                        context_files=changed_files,
                    )
                    futures[future] = name

                for future in as_completed(futures):
                    name = futures[future]
                    results[name] = future.result()
                    status = "✓" if results[name].success else "✗"
                    print(f"  {status} {name} complete")
        else:
            for name, agent_type in review_tasks:
                print(f"🔍 Running {name} agent...")
                results[name] = self.invoke_agent(
                    agent_type,
                    f"Review these changes:\n{code_summary}",
                    context_files=changed_files,
                )

        # Check for blockers
        if "security" in results and results["security"].blocked:
            print(f"⛔ Security blocked: {results['security'].block_reason}")
            if self.config.orchestrator.require_security_pass:
                return results

        # 3. Tests
        if not skip_tests and self.config.orchestrator.require_tests:
            tester_config = self.config.agents.get("tester")
            if tester_config is None or tester_config.enabled:
                print("🧪 Running tester agent...")
                test_result = self.invoke_agent(
                    AgentType.TESTER,
                    f"Write tests for these changes:\n{code_summary}",
                    context_files=changed_files,
                )
                results["tester"] = test_result

        print("✅ Pipeline complete")
        return results

    def plan_feature(self, feature_description: str) -> list[Task]:
        """
        Use the architect agent to plan a feature implementation.

        Returns a list of tasks to be executed.
        """
        # Start or update session
        if not self.state:
            self.start_session(feature_description)

        print("📐 Running architect agent for planning...")

        # Get architecture plan
        result = self.invoke_agent(
            AgentType.ARCHITECT,
            f"Plan the implementation for:\n\n{feature_description}\n\n"
            "Break this down into discrete tasks for: coder, reviewer, security, tester agents.",
        )

        if not result.success:
            print("❌ Architect failed to create plan")
            return []

        self.state.architecture = result.summary

        # Parse tasks from architect output
        tasks = []
        try:
            # Try to extract JSON from the summary
            import re

            json_match = re.search(r'"tasks"\s*:\s*\[(.*?)\]', result.summary, re.DOTALL)
            if json_match:
                # Parse the tasks array
                tasks_json = json.loads(f"[{json_match.group(1)}]")
                for i, t in enumerate(tasks_json):
                    task = Task(
                        id=self._generate_task_id(),
                        agent_type=AgentType(t.get("agent", "coder")),
                        description=t.get("task", ""),
                        context_files=t.get("context_files", []),
                        depends_on=t.get("depends_on", []),
                    )
                    tasks.append(task)
        except Exception:
            # Fallback: create a simple pipeline
            tasks = [
                Task(
                    id=self._generate_task_id(),
                    agent_type=AgentType.CODER,
                    description=f"Implement: {feature_description}",
                ),
                Task(
                    id=self._generate_task_id(),
                    agent_type=AgentType.SECURITY,
                    description="Security review",
                    depends_on=["task_001"],
                ),
                Task(
                    id=self._generate_task_id(),
                    agent_type=AgentType.REVIEWER,
                    description="Code review",
                    depends_on=["task_001"],
                ),
                Task(
                    id=self._generate_task_id(),
                    agent_type=AgentType.TESTER,
                    description="Write tests",
                    depends_on=["task_001"],
                ),
            ]

        self.state.tasks = tasks
        self._save_state()

        return tasks

    def execute_plan(self) -> dict[str, AgentResult]:
        """
        Execute the planned tasks in order.
        """
        if not self.state or not self.state.tasks:
            raise ValueError("No plan to execute. Run plan_feature first.")

        results = {}

        for task in self.state.tasks:
            # Check dependencies
            deps_met = all(
                any(t.id == dep and t.status == TaskStatus.COMPLETED for t in self.state.tasks)
                for dep in task.depends_on
            )

            if not deps_met:
                print(f"⏳ Skipping {task.id} - dependencies not met")
                continue

            if task.status != TaskStatus.PENDING:
                continue

            print(f"▶️  Executing {task.id} ({task.agent_type.value})")
            task.status = TaskStatus.RUNNING
            self._save_state()

            # Get context from completed tasks
            context = []
            for t in self.state.tasks:
                if t.status == TaskStatus.COMPLETED and t.result:
                    context.extend(t.result.files_changed)
                    context.extend(t.result.files_created)

            # Execute
            result = self.invoke_agent(
                task.agent_type,
                task.description,
                context_files=list(set(context + task.context_files)),
            )

            task.result = result
            task.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED

            if result.blocked:
                task.status = TaskStatus.BLOCKED
                print(f"⛔ {task.id} blocked: {result.block_reason}")

            results[task.id] = result
            self._save_state()

        return results

    def get_status(self) -> dict:
        """Get current swarm status."""
        if not self.state:
            return {"status": "no_session"}

        completed = sum(1 for t in self.state.tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in self.state.tasks if t.status == TaskStatus.FAILED)
        blocked = sum(1 for t in self.state.tasks if t.status == TaskStatus.BLOCKED)
        pending = sum(1 for t in self.state.tasks if t.status == TaskStatus.PENDING)

        return {
            "session_id": self.state.session_id,
            "feature": self.state.feature_description,
            "status": self.state.status,
            "tasks": {
                "total": len(self.state.tasks),
                "completed": completed,
                "failed": failed,
                "blocked": blocked,
                "pending": pending,
            },
            "blockers": self.state.blockers,
            "summaries_count": len(self.state.completed_summaries),
        }

    def interactive_mode(self):
        """
        Run the orchestrator in interactive mode.

        This allows the orchestrator itself to use Claude to make decisions,
        while keeping its context minimal by only loading summaries.
        """
        # Build minimal context for orchestrator
        context = f"# Current Session\n\nFeature: {self.state.feature_description}\n\n"

        if self.state.architecture:
            context += f"## Architecture\n{self.state.architecture[:500]}\n\n"

        context += "## Recent Activity\n"
        for summary in self.state.completed_summaries[-10:]:
            context += f"- {summary}\n"

        if self.state.blockers:
            context += "\n## Blockers\n"
            for blocker in self.state.blockers:
                context += f"- ⛔ {blocker}\n"

        # This would invoke Claude to decide next steps
        # For now, return the context that would be used
        return context
